"""
level.py – Endless procedural level generation for Walk the Line.

LevelGenerator streams terrain chunks ahead of the player on demand
and prunes old geometry behind them.  Call gen.update(player_x) once
per frame; read gen.segments / gen.walls / gen.stars each frame.

Levels can be loaded from JSON files in the levels/ directory.
See levels/default.json for the schema.  Use LevelGenerator.from_file(path)
or pass a config dict to the constructor.
"""

import json
import random

from spring_line import SpringLine
from constants   import SCREEN_H


# Built-in defaults (mirrors levels/default.json)
_DEFAULTS = {
    "min_y": 180,
    "max_y": SCREEN_H - 120,
    "star_every": 380,
    "gap_max": 115,
    "difficulty_distance": 5000,
    "first_flip_x": 2500,
    "flip_interval": [1400, 2200],
    "flip_approach": [120, 180],
    "flip_landing":  [120, 180],
    "wall_chance":   0.28,
    "enemy_chance":  0.30,
    "chunk_weights": {
        "flat":      [4, 1],
        "hill":      2,
        "valley":    2,
        "ramp_up":   2,
        "ramp_down": 2,
        "gap":       [1, 6],
    },
    "chunk_params": {
        "flat":      {"length": [80, 180]},
        "hill":      {"up_len": [100, 200], "peak_len": [60, 120], "down_len": [100, 200]},
        "valley":    {"down_len": [80, 160], "floor_len": [60, 100], "up_len": [80, 160]},
        "ramp_up":   {"length": [120, 220], "flat": [60, 120]},
        "ramp_down": {"length": [120, 220], "flat": [60, 120]},
        "gap":       {"approach": [80, 160], "landing": [60, 120],
                      "width_base": [55, 80], "width_scale": [25, 35]},
    },
}

_DEFAULT_OPENING = [
    {"type": "flat", "length": 220},
    {"type": "star"},
    {"type": "flat", "length": 120},
]


class LevelGenerator:
    LOOKAHEAD    = 2000   # generate this many px ahead of the player
    PRUNE_BEHIND = 1000   # discard terrain this far behind the player

    # ── constructors ─────────────────────────────────────────────────────────

    @classmethod
    def from_file(cls, path, start_x=0.0, start_y=None, gravity_flipped=False):
        """Load a level from a JSON file.  Falls back to built-in defaults for
        any keys that are missing from the file.

        Pass start_x / start_y when transitioning seamlessly mid-run; the
        scripted opening is skipped and generation begins at that position.
        Pass gravity_flipped to match the player's current gravity state.
        """
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        gen_cfg  = data.get("generation", {})
        opening  = data.get("opening", _DEFAULT_OPENING)
        return cls(generation=gen_cfg, opening=opening,
                   start_x=start_x, start_y=start_y,
                   gravity_flipped=gravity_flipped)

    def __init__(self, generation=None, opening=None, start_x=0.0, start_y=None,
                 gravity_flipped=False):
        # Merge caller-supplied config on top of built-in defaults
        cfg = dict(_DEFAULTS)
        if generation:
            cfg.update(generation)
            # Deep-merge nested dicts
            for key in ("chunk_weights", "chunk_params"):
                if key in generation:
                    merged = dict(_DEFAULTS[key])
                    merged.update(generation[key])
                    cfg[key] = merged

        self._cfg             = cfg
        self._min_y           = float(cfg["min_y"])
        self._max_y           = float(cfg["max_y"])
        self._star_every      = cfg["star_every"]
        self._gap_max         = cfg["gap_max"]
        self._diff_dist       = cfg["difficulty_distance"]

        self.segments = []
        self.walls    = []
        self.stars    = []

        self._rng             = random.Random()
        self._x               = float(start_x)
        self._y               = float(start_y) if start_y is not None else SCREEN_H * 0.64
        self._last_star_at    = float(start_x)
        self._path            = [(self._x, self._y)]
        self._player_x        = float(start_x)
        self._next_flip_x     = float(start_x) + float(cfg["first_flip_x"])
        self._no_wall_until   = float(start_x) + 200.0
        self._gravity_flipped = gravity_flipped  # tracks which side stars should appear on

        self.flip_triggers  = []   # list of world-x positions where gravity toggles
        self.enemy_spawns   = []   # list of (x, y) tuples consumed by main loop

        # Play the scripted opening, then fill the initial look-ahead buffer
        if start_x > 0:
            self._extend_to(start_x + self.LOOKAHEAD)
        else:
            self._play_opening(opening if opening is not None else _DEFAULT_OPENING)
            self._extend_to(self.LOOKAHEAD)

    # ── public API ────────────────────────────────────────────────────────

    def update(self, player_x):
        """Extend terrain ahead and prune behind the player."""
        self._player_x = player_x
        self._extend_to(player_x + self.LOOKAHEAD)
        self._prune_before(player_x - self.PRUNE_BEHIND)

    def take_enemy_spawns(self):
        """Return and clear all pending enemy spawn points."""
        spawns, self.enemy_spawns = self.enemy_spawns, []
        return spawns

    # ── internal: book-keeping ────────────────────────────────────────────

    def _extend_to(self, target_x):
        while self._x < target_x:
            if self._x >= self._next_flip_x:
                self._flip_section()   # safe flat run with trigger in the middle
            else:
                self._generate_chunk()
            # Flush if the unflushed path has grown too long; this ensures
            # there is always a committed segment near the player even when
            # no gap has been generated for a while.
            if (len(self._path) >= 2
                    and self._path[-1][0] - self._path[0][0] >= 600):
                self._flush()

    def _prune_before(self, min_x):
        self.segments     = [s for s in self.segments     if s.x2 > min_x]
        self.walls        = [w for w in self.walls        if w[0] + w[2] > min_x]
        self.stars        = [(sx, sy) for sx, sy in self.stars if sx > min_x]
        self.enemy_spawns = [(sx, sy) for sx, sy in self.enemy_spawns if sx > min_x]

    def _flush(self):
        """Commit the current path waypoints as a new SpringLine."""
        if len(self._path) >= 2:
            seg = SpringLine.from_path(self._path)
            self.segments.append(seg)
            # Occasionally add a wall obstacle on long flat sections,
            # but never within the safe zone around a flip trigger.
            length     = seg.x2 - seg.x1
            is_flat    = abs(seg.y2 - seg.y1) < 5
            past_start = seg.x1 >= 400
            wx         = seg.x1 + length * 0.55
            safe       = wx < self._no_wall_until
            if length > 200 and is_flat and past_start and not safe:
                if self._rng.random() < self._cfg["wall_chance"]:
                    wy = seg.y1 - 50
                    self.walls.append((wx, wy, 18, 50))
                elif self._rng.random() < self._cfg["enemy_chance"]:
                    ex = seg.x1 + length * self._rng.uniform(0.3, 0.7)
                    self.enemy_spawns.append((ex, seg.y1))
        self._path = [(self._x, self._y)]

    # ── internal: primitives ──────────────────────────────────────────────

    def _add_seg(self, length, dy=0):
        self._y = max(self._min_y, min(self._max_y, self._y + dy))
        self._x += length
        self._path.append((self._x, self._y))

    def _add_gap(self, width):
        self._flush()
        self._x += width
        self._path = [(self._x, self._y)]

    def _drop_star(self):
        offset = 52 if self._gravity_flipped else -52
        self.stars.append((self._x, self._y + offset))
        self._last_star_at = self._x

    def _star_if_due(self):
        if self._x - self._last_star_at >= self._star_every:
            self._drop_star()

    # ── internal: composable terrain chunks ───────────────────────────────

    def _flat(self, length):
        half = length // 2
        self._add_seg(half)
        self._star_if_due()
        self._add_seg(length - half)

    def _hill(self, up_len, peak_len, down_len, height):
        self._add_seg(up_len, -abs(height))
        self._add_seg(peak_len // 2)
        self._star_if_due()
        self._add_seg(peak_len - peak_len // 2)
        self._add_seg(down_len, abs(height))

    def _valley(self, down_len, floor_len, up_len, depth):
        self._add_seg(down_len, abs(depth))
        self._add_seg(floor_len // 2)
        self._star_if_due()
        self._add_seg(floor_len - floor_len // 2)
        self._add_seg(up_len, -abs(depth))

    def _gap(self, width, approach=80, landing=80):
        self._flat(approach)
        self._add_gap(width)
        self._flat(landing)

    def _flip_section(self):
        """Flat approach → flip trigger → flat landing, no gaps or walls nearby."""
        fi = self._cfg["flip_interval"]
        fa = self._cfg["flip_approach"]
        fl = self._cfg["flip_landing"]
        approach = self._rng.randint(fa[0], fa[1])
        landing  = self._rng.randint(fl[0], fl[1])
        self._flat(approach)
        # Trigger placed here: on flat ground, approach already behind it
        self.flip_triggers.append(self._x)
        self._gravity_flipped = not self._gravity_flipped
        self._next_flip_x   = self._x + self._rng.randint(fi[0], fi[1])
        self._no_wall_until = self._x + landing + 200   # clear zone ahead of trigger
        self._flat(landing)

    # ── internal: scripted opening ────────────────────────────────────────

    def _play_opening(self, commands):
        """Execute a list of scripted terrain commands before procedural gen."""
        for cmd in commands:
            t = cmd["type"]
            if t == "flat":
                self._flat(cmd.get("length", 120))
            elif t == "star":
                self._drop_star()
            elif t == "hill":
                h = self._r_height()
                self._hill(cmd.get("up_len", 100), cmd.get("peak_len", 80),
                           cmd.get("down_len", 100), cmd.get("height", h))
            elif t == "valley":
                d = self._r_height() // 2
                self._valley(cmd.get("down_len", 80), cmd.get("floor_len", 60),
                             cmd.get("up_len", 80), cmd.get("depth", d))
            elif t == "gap":
                self._gap(cmd.get("width", 70),
                          approach=cmd.get("approach", 80),
                          landing=cmd.get("landing", 80))
            elif t == "ramp_up":
                self._add_seg(cmd.get("length", 150), -abs(cmd.get("height", 50)))
                self._flat(cmd.get("flat", 80))
            elif t == "ramp_down":
                self._add_seg(cmd.get("length", 150), abs(cmd.get("height", 50)))
                self._flat(cmd.get("flat", 80))
            elif t == "flip":
                self.flip_triggers.append(self._x)
                self._gravity_flipped = not self._gravity_flipped
                fi = self._cfg["flip_interval"]
                self._next_flip_x   = self._x + self._rng.randint(fi[0], fi[1])
                self._no_wall_until = self._x + 200
        self._flush()

    # ── difficulty-scaled random helpers ──────────────────────────────────

    @property
    def _progress(self):
        """0 → 1, saturates at difficulty_distance px."""
        return min(self._player_x / float(self._diff_dist), 1.0)

    def _interp_weight(self, w):
        """A weight can be a single int or [start, end] interpolated by progress."""
        if isinstance(w, list):
            return w[0] + (w[1] - w[0]) * self._progress
        return float(w)

    def _r_gap(self):
        p   = self._progress
        gp  = self._cfg["chunk_params"]["gap"]
        wb  = gp["width_base"]
        ws  = gp["width_scale"]
        lo  = int(wb[0] + ws[0] * p)
        hi  = int(wb[1] + ws[1] * p)
        return self._rng.randint(lo, min(hi, self._gap_max))

    def _r_height(self):
        p  = self._progress
        lo = int(30 + 20 * p)
        hi = int(55 + 45 * p)
        return self._rng.randint(lo, hi)

    def _r(self, lo, hi):
        return self._rng.randint(lo, hi)

    # ── internal: chunk selector ──────────────────────────────────────────

    def _generate_chunk(self):
        cw = self._cfg["chunk_weights"]
        cp = self._cfg["chunk_params"]
        choices = []
        for name, w in cw.items():
            choices += [name] * max(1, int(self._interp_weight(w)))
        chunk = self._rng.choice(choices)

        if chunk == 'flat':
            r = cp["flat"]["length"]
            self._flat(self._r(r[0], r[1]))

        elif chunk == 'hill':
            p = cp["hill"]
            self._hill(self._r(*p["up_len"]), self._r(*p["peak_len"]),
                       self._r(*p["down_len"]), self._r_height())

        elif chunk == 'valley':
            p = cp["valley"]
            self._valley(self._r(*p["down_len"]), self._r(*p["floor_len"]),
                         self._r(*p["up_len"]), self._r_height() // 2)

        elif chunk == 'ramp_up':
            p = cp["ramp_up"]
            self._add_seg(self._r(*p["length"]), -self._r_height())
            self._flat(self._r(*p["flat"]))

        elif chunk == 'ramp_down':
            p = cp["ramp_down"]
            self._add_seg(self._r(*p["length"]), self._r_height())
            self._flat(self._r(*p["flat"]))

        elif chunk == 'gap':
            p = cp["gap"]
            self._gap(self._r_gap(),
                      approach=self._r(*p["approach"]),
                      landing=self._r(*p["landing"]))

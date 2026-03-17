"""
level.py – Endless procedural level generation for Walk the Line.

LevelGenerator streams terrain chunks ahead of the player on demand
and prunes old geometry behind them.  Call gen.update(player_x) once
per frame; read gen.segments / gen.walls / gen.stars each frame.
"""

import random

from spring_line import SpringLine
from constants   import SCREEN_H


_MIN_Y      = 180.0
_MAX_Y      = SCREEN_H - 120.0
_STAR_EVERY = 380   # place a star at least once every N px
_GAP_MAX    = 115   # widest gap (must be jumpable)


class LevelGenerator:
    LOOKAHEAD    = 2000   # generate this many px ahead of the player
    PRUNE_BEHIND = 1000   # discard terrain this far behind the player

    def __init__(self):
        self.segments = []
        self.walls    = []
        self.stars    = []

        self._rng             = random.Random()
        self._x               = 0.0
        self._y               = SCREEN_H * 0.64
        self._last_star_at    = 0.0
        self._path            = [(0.0, self._y)]
        self._player_x        = 0.0   # updated each frame for difficulty scaling
        self._next_flip_x     = 2500.0  # first gravity-flip trigger
        self._no_wall_until   = 0.0    # suppress walls near flip triggers
        self._gravity_flipped = False  # tracks which side stars should appear on

        self.flip_triggers  = []   # list of world-x positions where gravity toggles
        self.enemy_spawns   = []   # list of (x, y) tuples consumed by main loop

        # Safe opening, then fill the initial look-ahead buffer
        self._flat(220)
        self._drop_star()
        self._flat(120)
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
                if self._rng.random() < 0.28:
                    wy = seg.y1 - 50
                    self.walls.append((wx, wy, 18, 50))
                elif self._rng.random() < 0.30:
                    ex = seg.x1 + length * self._rng.uniform(0.3, 0.7)
                    self.enemy_spawns.append((ex, seg.y1))
        self._path = [(self._x, self._y)]

    # ── internal: primitives ──────────────────────────────────────────────

    def _add_seg(self, length, dy=0):
        self._y = max(_MIN_Y, min(_MAX_Y, self._y + dy))
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
        if self._x - self._last_star_at >= _STAR_EVERY:
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
        approach = self._rng.randint(120, 180)
        landing  = self._rng.randint(120, 180)
        self._flat(approach)
        # Trigger placed here: on flat ground, approach already behind it
        self.flip_triggers.append(self._x)
        self._gravity_flipped = not self._gravity_flipped
        self._next_flip_x   = self._x + self._rng.randint(1400, 2200)
        self._no_wall_until = self._x + landing + 200   # clear zone ahead of trigger
        self._flat(landing)

    # ── difficulty-scaled random helpers ──────────────────────────────────

    @property
    def _progress(self):
        """0 → 1, saturates at 5000 px."""
        return min(self._player_x / 5000.0, 1.0)

    def _r_gap(self):
        p  = self._progress
        lo = int(55 + 25 * p)
        hi = int(80 + 35 * p)
        return self._rng.randint(lo, min(hi, _GAP_MAX))

    def _r_height(self):
        p  = self._progress
        lo = int(30 + 20 * p)
        hi = int(55 + 45 * p)
        return self._rng.randint(lo, hi)

    def _r(self, lo, hi):
        return self._rng.randint(lo, hi)

    # ── internal: chunk selector ──────────────────────────────────────────

    def _generate_chunk(self):
        p = self._progress
        choices = (
            ['flat']      * max(1, int(4 - 3 * p)) +
            ['hill']      * 2 +
            ['valley']    * 2 +
            ['ramp_up']   * 2 +
            ['ramp_down'] * 2 +
            ['gap']       * max(1, int(1 + 5 * p))
        )
        chunk = self._rng.choice(choices)

        if chunk == 'flat':
            self._flat(self._r(80, 180))

        elif chunk == 'hill':
            self._hill(self._r(100, 200), self._r(60, 120),
                       self._r(100, 200), self._r_height())

        elif chunk == 'valley':
            self._valley(self._r(80, 160), self._r(60, 100),
                         self._r(80, 160), self._r_height() // 2)

        elif chunk == 'ramp_up':
            self._add_seg(self._r(120, 220), -self._r_height())
            self._flat(self._r(60, 120))

        elif chunk == 'ramp_down':
            self._add_seg(self._r(120, 220), self._r_height())
            self._flat(self._r(60, 120))

        elif chunk == 'gap':
            self._gap(self._r_gap(),
                      approach=self._r(80, 160),
                      landing=self._r(60, 120))

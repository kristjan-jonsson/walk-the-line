"""
clouds.py – Chalk-sketch clouds and rain for Walk the Line.

Clouds are drawn as overlapping circle outlines (no fill), matching the
minimalist white line-art style of the rest of the game.  Rain is short
white falling lines.

The system streams ahead of the player with random density — sometimes
sparse sky, sometimes thick clusters.  Clouds scroll at a slower parallax
rate than the terrain for a gentle sense of depth.
"""

import math
import random
import pygame

from constants import SCREEN_W, SCREEN_H

WHITE    = (255, 255, 255)
_LW      = 3      # stroke width matching the main terrain line
_PARALLAX = 0.65  # clouds scroll at 65 % of the camera — gentle depth layer


class _Cloud:
    def __init__(self, world_x, y, rng):
        self.world_x = float(world_x)
        self.y       = float(y)

        # ── bumps (overlapping circles define the cloud shape) ────────────
        n_bumps = rng.randint(3, 6)
        self.bumps = []   # list of (dx, dy, radius) relative to (world_x, y)
        cx = 0
        for i in range(n_bumps):
            r  = rng.randint(14, 30)
            dy = rng.randint(-r // 2, r // 4)
            self.bumps.append((cx, dy, r))
            # next bump overlaps slightly
            cx += rng.randint(r - 6, r + 14)
        self.width = cx + self.bumps[-1][2]

        # ── rain ──────────────────────────────────────────────────────────
        self.has_rain = rng.random() < 0.1
        self.drops    = []   # (dx, length, phase, speed)
        if self.has_rain:
            n_drops = rng.randint(8, 18)
            # spread drops across the cloud width
            for _ in range(n_drops):
                dx     = rng.uniform(4, max(5, self.width - 4))
                length = rng.randint(9, 20)
                phase  = rng.uniform(0, 52)   # stagger so drops don't fall in sync
                speed  = rng.uniform(0.9, 1.8)
                self.drops.append((dx, length, phase, speed))

        # Lowest point of any bump – rain starts just below this
        self._rain_top_dy = max(dy + r for _, dy, r in self.bumps) + 6

    def draw(self, surface, cam_x, tick):
        # Parallax: cloud's apparent screen-x moves slower than the terrain
        sx = int(self.world_x - cam_x * _PARALLAX)
        sy = int(self.y)

        # ── cloud body – overlapping circle outlines ───────────────────────
        for dx, dy, r in self.bumps:
            pygame.draw.circle(surface, WHITE, (sx + dx, sy + dy), r, _LW)

        # ── rain – short falling lines that loop within a 55 px belt ──────
        if self.has_rain:
            rain_top = sy + self._rain_top_dy
            for dx, length, phase, speed in self.drops:
                # cycle the drop through a 55 px window then restart
                offset = (tick * speed * 0.55 + phase) % 55
                x1 = sx + int(dx)
                y1 = rain_top + int(offset)
                # slight rightward slant feels more natural
                pygame.draw.line(surface, WHITE,
                                 (x1,     y1),
                                 (x1 + 2, y1 + length), max(1, _LW - 1))


class CloudSystem:
    """Streams clouds ahead of the player; prunes old ones behind."""

    _LOOKAHEAD    = 1800
    _PRUNE_BEHIND = 900

    def __init__(self):
        self._rng    = random.Random()
        self._next_x = 250.0
        self.clouds  = []
        self._extend_to(self._LOOKAHEAD)

    # ── public API ────────────────────────────────────────────────────────

    def update(self, player_x, cam_x):
        # Clouds live in world-space but render with parallax; use the
        # parallax-adjusted camera position so extend/prune are correct.
        apparent_x = cam_x * _PARALLAX
        self._extend_to(apparent_x + self._LOOKAHEAD)
        self._prune_before(apparent_x - self._PRUNE_BEHIND)

    def draw(self, surface, cam_x, tick):
        for cloud in self.clouds:
            # Quick cull before calling draw
            sx = cloud.world_x - cam_x * _PARALLAX
            if sx + cloud.width < -10 or sx > SCREEN_W + 10:
                continue
            cloud.draw(surface, cam_x, tick)

    # ── internal ──────────────────────────────────────────────────────────

    def _extend_to(self, target_x):
        while self._next_x < target_x:
            # Dense cluster (20 % chance) or normal gap
            if self._rng.random() < 0.20:
                gap = self._rng.randint(10, 60)   # clouds packed close together
            else:
                gap = self._rng.randint(90, 520)  # sparse open sky

            self._next_x += gap
            y = self._rng.randint(50, 200)
            self.clouds.append(_Cloud(self._next_x, y, self._rng))

    def _prune_before(self, min_x):
        self.clouds = [c for c in self.clouds if c.world_x + c.width > min_x]

"""
level.py – Procedural level generation for La Linea.

generate_level() returns a fresh random level every call:
  segments  : list[SpringLine]  – spring-physics terrain sections
  stars     : list[(x, y)]      – collectible star world positions
  level_end : float             – x coordinate of the finish line

Internal helpers:
  add_seg(length, dy=0)  – extend the current connected section
  add_gap(width)         – break the line (gap to jump over)
  flat(length)           – flat stretch, drops a star if one is due
  hill(up, peak, down)   – rise → flat peak → fall
  gap(width)             – flat approach + gap + flat landing
"""

import random

from spring_line import SpringLine
from constants   import SCREEN_H


# ── Tuneable limits ────────────────────────────────────────────────────────────
_MIN_Y      = 180.0            # highest the line may go (px from top)
_MAX_Y      = SCREEN_H - 120.0 # lowest the line may go
_STAR_EVERY = 380              # drop a star at least once every N px
_GAP_MAX    = 115              # widest gap (must be jumpable)


def generate_level():
    """Return (segments, stars, level_end) for a freshly randomised level."""
    rng    = random.Random()   # unseeded → different every run
    GROUND = SCREEN_H * 0.64

    segments = []
    stars    = []
    x, y     = 0.0, GROUND
    path     = [(0.0, GROUND)]
    last_star_at = 0.0         # x position of last star placed

    # ── low-level primitives ──────────────────────────────────────────────

    def flush():
        if len(path) >= 2:
            segments.append(SpringLine.from_path(path))
        path.clear()

    def add_seg(length, dy=0):
        nonlocal x, y
        y = max(_MIN_Y, min(_MAX_Y, y + dy))
        x += length
        path.append((x, y))

    def add_gap(width):
        nonlocal x
        flush()
        x += width
        path.append((x, y))

    def drop_star():
        nonlocal last_star_at
        stars.append((x, y - 52))
        last_star_at = x

    def star_if_due():
        if x - last_star_at >= _STAR_EVERY:
            drop_star()

    # ── composable terrain chunks ─────────────────────────────────────────

    def flat(length):
        half = length // 2
        add_seg(half)
        star_if_due()
        add_seg(length - half)

    def hill(up_len, peak_len, down_len, height):
        """Rise by -height, flat peak, fall back down."""
        add_seg(up_len, -abs(height))
        add_seg(peak_len // 2)
        star_if_due()
        add_seg(peak_len - peak_len // 2)
        add_seg(down_len, abs(height))

    def valley(down_len, floor_len, up_len, depth):
        """Dip by +depth, flat floor, rise back up."""
        add_seg(down_len, abs(depth))
        add_seg(floor_len // 2)
        star_if_due()
        add_seg(floor_len - floor_len // 2)
        add_seg(up_len, -abs(depth))

    def gap(width, approach=80, landing=80):
        flat(approach)
        add_gap(width)
        flat(landing)

    def ramp_up(length, height):
        add_seg(length, -abs(height))

    def ramp_down(length, height):
        add_seg(length, abs(height))

    # ── difficulty-scaled random pickers ─────────────────────────────────

    def r_gap(progress):
        """Gap width scales from small early to large late."""
        lo = int(55 + 25 * progress)
        hi = int(80 + 35 * progress)
        return rng.randint(lo, min(hi, _GAP_MAX))

    def r_height(progress):
        """Slope height scales with progress."""
        lo = int(30 + 20 * progress)
        hi = int(55 + 45 * progress)
        return rng.randint(lo, hi)

    def r_len(lo, hi):
        return rng.randint(lo, hi)

    # ── level assembly ────────────────────────────────────────────────────

    # Safe opening – always flat so the player gets their bearings
    flat(220)
    drop_star()
    flat(120)

    TARGET = 3400   # total level length before finish runway

    while x < TARGET:
        progress = min(x / TARGET, 1.0)

        # Weight each chunk type: gaps become more common with progress
        choices = (
            ['flat']         * max(1, int(4 - 3 * progress)) +
            ['hill']         * 2 +
            ['valley']       * 2 +
            ['ramp_up']      * 2 +
            ['ramp_down']    * 2 +
            ['gap']          * max(1, int(1 + 5 * progress))
        )
        chunk = rng.choice(choices)

        if chunk == 'flat':
            flat(r_len(80, 180))

        elif chunk == 'hill':
            hill(r_len(100, 200), r_len(60, 120), r_len(100, 200),
                 r_height(progress))

        elif chunk == 'valley':
            valley(r_len(80, 160), r_len(60, 100), r_len(80, 160),
                   r_height(progress) // 2)

        elif chunk == 'ramp_up':
            ramp_up(r_len(120, 220), r_height(progress))
            flat(r_len(60, 120))

        elif chunk == 'ramp_down':
            ramp_down(r_len(120, 220), r_height(progress))
            flat(r_len(60, 120))

        elif chunk == 'gap':
            gap(r_gap(progress),
                approach=r_len(80, 160),
                landing=r_len(60, 120))

    # Finish runway – always ends on flat ground
    add_seg(80, int((GROUND - y) * 0.4))   # gentle slope back toward GROUND
    flat(60)
    drop_star()
    flat(200)

    flush()
    return segments, stars, x

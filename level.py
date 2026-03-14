"""
level.py – Level layout and generation for La Linea.

Defines generate_level(), which returns:
  segments  : list[SpringLine]  – spring-physics terrain sections
  stars     : list[(x, y)]      – collectible star world positions
  level_end : float             – x coordinate of the finish line

The layout uses three helpers:
  add_seg(length, dy=0)  – extend the current connected section
  add_gap(width)         – break the line (gap to jump over)
  add_star(ox=0, oy=-52) – place a star at the current position

Stars are always placed with ox=0 so their y matches the actual ground
at that x, making every star reachable while walking (no jump needed).
"""

from spring_line import SpringLine
from constants   import SCREEN_W, SCREEN_H


def generate_level():
    """Return (segments, stars, level_end) for the single built-in level."""
    GROUND = SCREEN_H * 0.64
    segments = []
    stars    = []
    x, y     = 0.0, GROUND
    path     = [(0.0, GROUND)]   # waypoints for the current connected section

    # ── internal helpers ──────────────────────────────────────────────────

    def flush():
        if len(path) >= 2:
            segments.append(SpringLine.from_path(path))
        path.clear()

    def add_seg(length, dy=0):
        nonlocal x, y
        new_y = max(180.0, min(SCREEN_H - 120.0, y + dy))
        x    += length
        y     = new_y
        path.append((x, y))

    def add_gap(width):
        nonlocal x
        flush()
        x += width
        path.append((x, y))     # resume at same height after the gap

    def add_star(ox=0, oy=-52):
        stars.append((x + ox, y + oy))

    # ── level layout ──────────────────────────────────────────────────────
    # Stars are placed at ox=0 (current x) so their y always matches the
    # ground at that exact point – all reachable while walking.

    add_seg(200)
    add_star(0, -52)           # 1 — opening runway
    add_seg(120)               # total flat: 320

    add_seg(180, -50)          # rise
    add_seg(70)
    add_star(0, -52)           # 2 — top of the rise
    add_seg(50)                # total flat after rise: 120
    add_gap(90)                # gap 1

    add_seg(80)
    add_star(0, -52)           # 3 — just after gap 1
    add_seg(80)                # total: 160

    add_seg(200, 60)           # dip down
    add_seg(40)
    add_star(0, -52)           # 4 — bottom of the dip
    add_seg(40)
    add_gap(70)                # gap 2
    add_seg(80)

    add_seg(160, -80)          # climb
    add_seg(80)
    add_star(0, -52)           # 5 — near the peak
    add_seg(60)                # total flat: 140
    add_gap(110)               # wide gap — need a run-up

    add_seg(200, 30)
    add_seg(60)
    add_star(0, -52)           # 6 — mid-level descent
    add_seg(60)                # total flat: 120

    add_seg(200, -90)          # tall hill
    add_seg(60)
    add_gap(60)
    add_seg(200, 110)          # long descent

    add_seg(100)
    add_star(0, -52)           # 7 — bottom of long descent
    add_seg(80)                # total flat: 180
    add_gap(80)

    add_seg(150, -40)
    add_seg(100)
    add_gap(55)
    add_seg(100, 40)

    add_seg(160)
    add_star(0, -52)           # 8 — finish runway
    add_seg(190)               # total finish: 350

    flush()                    # commit the final section
    level_end = x
    return segments, stars, level_end

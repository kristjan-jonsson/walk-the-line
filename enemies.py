"""
enemies.py – Chalk-art enemies and heart HUD for Walk the Line.

Enemies patrol the terrain line and chase the player when close.
Contact costs the player a life.  The player can stomp an enemy by
landing on it from above (normal gravity only).

Drawing style: white outline only, no fill — matching the rest of the game.
"""

import math
import pygame

from constants import SCREEN_W

WHITE = (255, 255, 255)
_DIM  = (120, 120, 120)   # used for lost hearts
_LW   = 3


# ── Heart HUD ─────────────────────────────────────────────────────────────────

def _heart_pts(cx, cy, r):
    """Parametric chalk heart polygon centred at (cx, cy), radius ≈ r."""
    pts = []
    for i in range(30):
        t = 2 * math.pi * i / 30
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t)
              - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((cx + x * r / 16, cy + y * r / 14))
    return pts


def draw_hearts(surface, lives, max_lives=3):
    """Draw chalk hearts below the star counter (top-left)."""
    r   = 11
    gap = 30
    x0  = 20
    y0  = 58
    for i in range(max_lives):
        cx  = x0 + i * gap + r
        pts = _heart_pts(cx, y0, r)
        if i < lives:
            pygame.draw.polygon(surface, WHITE, pts)        # filled = alive
        else:
            pygame.draw.polygon(surface, _DIM, pts, 2)     # dim outline = lost


# ── Enemy ─────────────────────────────────────────────────────────────────────

class Enemy:
    _PATROL_SPEED = 1.4
    _CHASE_SPEED  = 3.2
    _CHASE_RANGE  = 150   # px – start chasing
    _HIT_RANGE    = 22    # px – contact distance that deals damage
    _HIT_COOLDOWN = 90    # frames between consecutive hits

    def __init__(self, x, y):
        self.x         = float(x)
        self.y         = float(y)   # foot / contact y (kept in sync with terrain)
        self.vx        = self._PATROL_SPEED
        self.patrol_cx = float(x)
        self.patrol_r  = 110
        self.alive     = True
        self.state     = 'patrol'   # 'patrol' | 'chase'
        self._walk_t   = 0
        self._walk_f   = 0          # walk-frame 0–3
        self._hit_cd   = 0

    # ── logic ──────────────────────────────────────────────────────────────

    def update(self, player_x, player_y, segments):
        if not self.alive:
            return

        self._walk_t += 1
        if self._walk_t % 8 == 0:
            self._walk_f = (self._walk_f + 1) % 4
        if self._hit_cd > 0:
            self._hit_cd -= 1

        dx   = player_x - self.x
        dist = abs(dx)

        if dist < self._CHASE_RANGE:
            self.state = 'chase'
        elif abs(self.x - self.patrol_cx) > self.patrol_r:
            self.state = 'patrol'
            self.vx = -self.vx   # bounce at patrol edge

        if self.state == 'chase':
            self.vx = math.copysign(self._CHASE_SPEED, dx)
        else:
            self.vx = math.copysign(self._PATROL_SPEED, self.vx)

        self.x += self.vx

        # Snap y to terrain surface
        for seg in segments:
            if seg.contains_x(self.x):
                self.y = seg.y_at(self.x)
                break

    def can_hit(self):
        return self._hit_cd == 0

    def register_hit(self):
        self._hit_cd = self._HIT_COOLDOWN

    def hits_player(self, px, py):
        return (self.alive
                and abs(self.x - px) < self._HIT_RANGE
                and abs(self.y - py) < 44)

    def stomped_by(self, px, py, pvy):
        """Player lands on enemy from above (normal gravity only)."""
        return (self.alive
                and pvy > 1.5
                and abs(self.x - px) < 28
                and 0 <= py - self.y <= 18)

    # ── draw ───────────────────────────────────────────────────────────────

    def draw(self, surface, cam_x):
        if not self.alive:
            return
        sx = int(self.x - cam_x)
        sy = int(self.y)
        if sx < -60 or sx > SCREEN_W + 60:
            return

        fd      = 1 if self.vx >= 0 else -1
        chasing = self.state == 'chase'
        wa      = math.sin(self._walk_f * math.pi / 2) * 14

        # ── body (circle) ─────────────────────────────────────────────────
        body_r  = 13
        body_cy = sy - 18
        pygame.draw.circle(surface, WHITE, (sx, body_cy), body_r, _LW)

        # Spikes – longer + more when chasing
        n_spk    = 8 if chasing else 6
        spk_len  = 10 if chasing else 6
        for k in range(n_spk):
            a     = 2 * math.pi * k / n_spk
            tip_x = sx + int(math.cos(a) * (body_r + spk_len))
            tip_y = body_cy + int(math.sin(a) * (body_r + spk_len))
            bl_x  = sx + int(math.cos(a + 0.32) * body_r)
            bl_y  = body_cy + int(math.sin(a + 0.32) * body_r)
            br_x  = sx + int(math.cos(a - 0.32) * body_r)
            br_y  = body_cy + int(math.sin(a - 0.32) * body_r)
            pygame.draw.polygon(surface, WHITE,
                                [(tip_x, tip_y), (bl_x, bl_y), (br_x, br_y)], _LW)

        # ── eye ───────────────────────────────────────────────────────────
        eye_r = 3 if chasing else 2
        pygame.draw.circle(surface, WHITE,
                           (sx + fd * 5, body_cy - 2), eye_r, 0)
        # angry brow
        brow_y = body_cy - eye_r - 5
        pygame.draw.line(surface, WHITE,
                         (sx + fd * 2, brow_y + 2),
                         (sx + fd * 8, brow_y), _LW)

        # ── legs ──────────────────────────────────────────────────────────
        leg_w = 10
        hip_y = sy - 5
        for is_front, swing in ((True, wa), (False, -wa)):
            root_x  = sx + fd * (3 if is_front else -3)
            ankle_x = root_x + fd * int(swing * 0.4)
            leg_pts = [
                (root_x  - leg_w // 2, hip_y),
                (root_x  + leg_w // 2, hip_y),
                (ankle_x + leg_w // 2, sy - 3),
                (ankle_x - leg_w // 2, sy - 3),
            ]
            pygame.draw.polygon(surface, WHITE, leg_pts, _LW)

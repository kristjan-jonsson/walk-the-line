"""
character.py – Mr. Linea player character for La Linea.

MrLinea handles physics, collision, animation, and drawing.
Call char.update(...) once per frame; read sound-event flags
(ev_jump, ev_land, ev_step, ev_star, ev_die) each frame then clear them.
"""

import math
import pygame

from constants import SCREEN_H, GRAVITY, JUMP_FORCE, MOVE_SPEED

WHITE = (255, 255, 255)


class MrLinea:
    """The iconic line-drawn character."""

    CHAR_H = 52   # feet-to-crown height
    CHAR_W = 14   # half-width for wall collisions

    def __init__(self, x, y):
        self.x  = float(x)   # feet x
        self.y  = float(y)   # feet y
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground   = False
        self.facing_right = True
        self.walk_timer  = 0
        self.walk_frame  = 0
        self.alive       = True
        self.stars_collected = 0
        # Sound-event flags – read by main loop each frame, then cleared
        self.ev_jump  = False
        self.ev_land  = False
        self.ev_step  = False
        self.ev_star  = False
        self.ev_die   = False

    # ── physics & collision ───────────────────────────────────────────────

    def update(self, segments, walls, keys, stars_list):
        if not self.alive:
            return

        # Horizontal input
        moving = False
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.vx = MOVE_SPEED
            self.facing_right = True
            moving = True
        elif keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.vx = -MOVE_SPEED * 0.75
            self.facing_right = False
            moving = True
        else:
            self.vx *= 0.82   # friction

        # Jump
        if (keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]) and self.on_ground:
            self.vy = JUMP_FORCE
            self.on_ground = False
            self.ev_jump = True

        # Remember whether we were on the ground before this frame
        was_on_ground = self.on_ground

        # Gravity
        self.vy += GRAVITY

        # Track y before movement so swept collision can detect tunneling
        prev_y = self.y

        # Integrate
        self.x += self.vx
        self.y += self.vy

        # ── terrain collision ────────────────────────────────────────────
        # Two passes: swept (landing / tunneling) and slope-follow (uphill).
        self.on_ground = False
        best_gy   = float('inf')
        best_line = None

        for seg in segments:
            margin = 4
            if not (seg.contains_x(self.x) or seg.contains_x(self.x - margin) or seg.contains_x(self.x + margin)):
                continue
            cx  = max(seg.x1, min(seg.x2, self.x))
            gy  = seg.y_at(cx)

            # Swept: character crossed from above to below this frame
            swept  = prev_y <= gy + 1 and self.y >= gy - 1
            # Slope-follow: already on ground and slope rose/fell beneath us
            #   self.y - gy > 0  → uphill (character clipped into rising slope)
            #   gy - self.y > 0  → downhill (character floating above descending slope)
            follow = was_on_ground and (self.y - gy) <= 20 and (gy - self.y) <= 10

            if (swept or follow) and self.vy >= 0:
                if gy < best_gy:
                    best_gy   = gy
                    best_line = seg

        if best_line is not None and self.vy >= 0:
            # Landing impulse (bigger when falling fast) + constant weight while walking
            force = self.vy * 0.30 + 0.40
            best_line.apply_force(self.x, force)
            self.y  = best_gy
            self.vy = 0.0
            self.on_ground = True
            if not was_on_ground:
                self.ev_land = True

        # ── wall collision ───────────────────────────────────────────────
        for wall in walls:
            wx, wy, ww, wh = wall
            # AABB: character feet at (self.x, self.y), body spans [-CHAR_W, CHAR_W] x [-CHAR_H, 0]
            char_left  = self.x - self.CHAR_W
            char_right = self.x + self.CHAR_W
            char_top   = self.y - self.CHAR_H
            char_bot   = self.y

            wall_left  = wx
            wall_right = wx + ww
            wall_top   = wy
            wall_bot   = wy + wh

            if char_right > wall_left and char_left < wall_right and char_bot > wall_top and char_top < wall_bot:
                # Push out horizontally
                overlap_r = char_right - wall_left
                overlap_l = wall_right - char_left
                if overlap_r < overlap_l:
                    self.x -= overlap_r
                    self.vx = 0
                else:
                    self.x += overlap_l
                    self.vx = 0

        # ── star collection ──────────────────────────────────────────────
        for star in stars_list[:]:
            sx, sy = star
            if abs(self.x - sx) < 24 and abs(self.y - sy - 40) < 24:
                stars_list.remove(star)
                self.stars_collected += 1
                self.ev_star = True

        # ── walk animation ───────────────────────────────────────────────
        if self.on_ground and abs(self.vx) > 0.5:
            self.walk_timer += 1
            if self.walk_timer >= 8:
                self.walk_timer = 0
                self.walk_frame = (self.walk_frame + 1) % 4
                if self.walk_frame in (0, 2):   # every other step
                    self.ev_step = True
        elif self.on_ground:
            self.walk_frame = 0

        # ── death ────────────────────────────────────────────────────────
        if self.y > SCREEN_H + 100:
            self.alive = False
            self.ev_die = True

    # ── drawing ──────────────────────────────────────────────────────────

    def draw(self, surface, cam_x):
        if not self.alive:
            return
        sx = int(self.x - cam_x)
        sy = int(self.y)
        self._draw_at(surface, sx, sy)

    def _draw_at(self, surface, sx, sy, color=WHITE, lw=3):
        """Draw Mr. Linea centred at foot position (sx, sy)."""
        fr = self.facing_right

        # ── head ─────────────────────────────────────────────────────────
        hx, hy = sx, sy - 42
        pygame.draw.circle(surface, color, (hx, hy), 13, lw)

        # ── nose (the iconic feature) ─────────────────────────────────────
        if fr:
            nose = [(hx + 11, hy - 1), (hx + 27, hy + 5), (hx + 11, hy + 10)]
        else:
            nose = [(hx - 11, hy - 1), (hx - 27, hy + 5), (hx - 11, hy + 10)]
        pygame.draw.polygon(surface, color, nose, lw)

        # ── body ─────────────────────────────────────────────────────────
        body_top = hy + 13
        body_bot = sy - 10
        body_pts = []
        steps = 16
        for i in range(steps + 1):
            t = i / steps
            angle = math.pi * t
            bx = hx - 11 * math.sin(angle)
            by = body_top + t * (body_bot - body_top)
            body_pts.append((int(bx), int(by)))
        for i in range(steps + 1):
            t = i / steps
            angle = math.pi * (1 - t)
            bx = hx + 11 * math.sin(angle)
            by = body_bot - t * (body_bot - body_top)
            body_pts.append((int(bx), int(by)))
        if len(body_pts) > 2:
            pygame.draw.polygon(surface, color, body_pts, lw)

        # ── arms ─────────────────────────────────────────────────────────
        arm_y   = body_top + (body_bot - body_top) * 0.35
        swing   = math.sin(self.walk_frame * math.pi / 2) * 13 if self.on_ground else 0
        pygame.draw.line(surface, color, (hx - 9, int(arm_y)), (hx - 22, int(arm_y + 14 + swing)), lw)
        pygame.draw.line(surface, color, (hx + 9, int(arm_y)), (hx + 22, int(arm_y + 14 - swing)), lw)

        # ── legs ─────────────────────────────────────────────────────────
        leg_s = math.sin(self.walk_frame * math.pi / 2) * 11 if self.on_ground else 0
        fd    = 1 if fr else -1

        for side, leg_shift in ((-1, -leg_s), (1, leg_s)):
            lx_top = hx + side * 5
            lx_bot = hx + side * 7 + int(leg_shift)
            pygame.draw.line(surface, color, (lx_top, body_bot), (lx_bot, sy), lw)
            # foot
            pygame.draw.line(surface, color, (lx_bot, sy), (lx_bot + fd * 11, sy), lw)

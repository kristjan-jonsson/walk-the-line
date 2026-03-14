"""
character.py – Mr. Linea player character.

MrLinea handles physics, collision, animation, and drawing.
Call char.update(...) once per frame; read sound-event flags
(ev_jump, ev_land, ev_step, ev_star, ev_die) each frame then clear them.

Drawing uses pre-rendered sprite Surfaces keyed by (frame_name, facing_right).
Visual style: profile-view line-art with the body drawn as one unified silhouette
polygon and legs drawn as closed tubular outlines (hollow interior visible).
"""

import math
import pygame

from constants import SCREEN_H, GRAVITY, JUMP_FORCE, MOVE_SPEED

WHITE = (255, 255, 255)

# ── Sprite canvas constants ───────────────────────────────────────────────────
_SW  = 84    # surface width
_SH  = 62    # surface height
_SAX = 38    # foot-anchor x within the surface
_SAY = 56    # foot-anchor y within the surface
_LW  = 3     # stroke width used throughout


# ── Standalone frame renderer ─────────────────────────────────────────────────

def _draw_frame(surf, fx, fy, facing_right, walk_angle, airborne=False):
    """
    Render one pose onto *surf* with the foot-point at (fx, fy).

    The character is drawn in profile view:
      • Head + body form a single connected outline polygon.
      • Each leg is a separate closed polygon outline so the background
        shows through the hollow interior ("space inside the legs").
      • Arms are simple lines with a slight walk-cycle swing.
    """
    fd = 1 if facing_right else -1
    c  = WHITE
    lw = _LW

    # ── Vertical landmarks (measured upward from foot) ────────────────────────
    hip_y   = fy - 11    # hip / leg root
    waist_y = fy - 22    # narrowest body point
    chest_y = fy - 33    # chest / arm root
    neck_y  = fy - 40    # top of body polygon / base of head
    head_cy = fy - 43    # head centre
    head_r  = 10         # head radius  (head top ≈ fy-53, within CHAR_H=54)

    # ── Walk-cycle values ─────────────────────────────────────────────────────
    if airborne:
        front_swing, back_swing = 15, -8    # legs tucked/spread in the air
        arm_lift = 18                        # arms raised during jump
        arm_swing = 0
    else:
        s = math.sin(walk_angle) * 16
        front_swing, back_swing = s, -s
        arm_lift  = 0
        arm_swing = math.sin(walk_angle) * 13

    # ── LEGS (drawn before body; body bottom will visually cap them) ──────────
    # Each leg is a closed polygon outline → hollow interior = "space inside".
    # Painter's order: back leg first so front leg overlaps it.
    leg_w = 14   # tube width; with lw=3 the visible interior is ~8 px wide

    for is_front, swing in ((False, back_swing), (True, front_swing)):
        # Hip attachment – front and back leg roots are offset slightly in x
        root_x = fx + fd * (4 if is_front else -3)

        # Ankle position swings forward/back with walk phase
        ankle_x = root_x + fd * int(swing)
        ankle_y = fy

        # Foot: toe extends forward in fd direction, short heel behind
        toe_x  = ankle_x + fd * 12
        heel_x = ankle_x - fd * 3

        leg_pts = [
            (root_x - leg_w // 2,   hip_y    ),   # inner hip
            (root_x + leg_w // 2,   hip_y    ),   # outer hip
            (ankle_x + leg_w // 2,  ankle_y - 4), # outer ankle
            (toe_x,                 ankle_y  ),   # toe tip
            (heel_x,                ankle_y  ),   # heel
            (ankle_x - leg_w // 2,  ankle_y - 4), # inner ankle
        ]
        # lw > 0 → outline only, interior is transparent (the "space inside")
        pygame.draw.polygon(surf, c, leg_pts, lw)

    # ── BODY – one unified profile silhouette polygon ─────────────────────────
    # Traces the front of the torso from neck, down chest/belly, through the
    # crotch, back up the spine to the neck again.  All in one closed outline.
    body_pts = [
        (fx,            neck_y      ),   # crown of body / base of neck
        (fx + fd *  5,  neck_y  + 3 ),   # front shoulder
        (fx + fd * 12,  chest_y + 7 ),   # chest bulge
        (fx + fd * 10,  waist_y     ),   # belly
        (fx + fd *  8,  hip_y       ),   # hip front
        (fx,            hip_y   + 5 ),   # crotch
        (fx - fd *  8,  hip_y       ),   # hip back
        (fx - fd *  9,  waist_y     ),   # lower back
        (fx - fd *  6,  chest_y + 5 ),   # upper back
        (fx - fd *  3,  neck_y  + 2 ),   # back shoulder
    ]
    pygame.draw.polygon(surf, c, body_pts, lw)

    # ── ARMS ─────────────────────────────────────────────────────────────────
    arm_root_y = chest_y + 6
    # Front arm (on the facing side)
    pygame.draw.line(surf, c,
        (fx + fd * 10,  arm_root_y),
        (fx + fd * 17,  arm_root_y + 14 + int(arm_swing) - arm_lift), lw)
    # Back arm
    pygame.draw.line(surf, c,
        (fx - fd *  4,  arm_root_y + 2),
        (fx - fd * 12,  arm_root_y + 14 - int(arm_swing) - arm_lift), lw)

    # ── HEAD ─────────────────────────────────────────────────────────────────
    # Drawn last so it sits on top of body and arms.
    pygame.draw.circle(surf, c, (fx, head_cy), head_r, lw)

    # Eye – single filled dot on the forward side of the face
    pygame.draw.circle(surf, c, (fx + fd * 4, head_cy - 4), 2, 0)

    # Nose – a rounded forward bump drawn as a small closed polygon
    nose_pts = [
        (fx + fd * (head_r - 2),  head_cy + 2 ),
        (fx + fd * (head_r + 9),  head_cy + 3 ),
        (fx + fd * (head_r + 12), head_cy + 7 ),
        (fx + fd * (head_r + 9),  head_cy + 13),
        (fx + fd * (head_r - 2),  head_cy + 12),
    ]
    pygame.draw.polygon(surf, c, nose_pts, lw)


# ── Character class ───────────────────────────────────────────────────────────

class MrLinea:
    """Profile line-art character with physics, collision, and sprite animation."""

    CHAR_H = 54   # feet-to-crown height (used for collision geometry)
    CHAR_W = 14   # half-width for wall collisions

    def __init__(self, x, y):
        self.x  = float(x)   # feet x
        self.y  = float(y)   # feet y
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground       = False
        self.facing_right    = True
        self.walk_timer      = 0
        self.walk_frame      = 0
        self.alive           = True
        self.stars_collected = 0
        # Sound-event flags – read by main loop each frame, then cleared
        self.ev_jump = False
        self.ev_land = False
        self.ev_step = False
        self.ev_star = False
        self.ev_die  = False
        # Sprite cache – populated lazily on first draw (needs display surface)
        self._sprites = None

    # ── Physics & collision ───────────────────────────────────────────────────

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

        was_on_ground = self.on_ground

        # Gravity
        self.vy += GRAVITY

        # Track y before movement so swept collision can detect tunneling
        prev_y = self.y

        # Integrate
        self.x += self.vx
        self.y += self.vy

        # ── Terrain collision ─────────────────────────────────────────────────
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

        # ── Wall collision ────────────────────────────────────────────────────
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

        # ── Star collection ───────────────────────────────────────────────────
        for star in stars_list[:]:
            sx, sy = star
            if abs(self.x - sx) < 24 and abs(self.y - sy - 40) < 24:
                stars_list.remove(star)
                self.stars_collected += 1
                self.ev_star = True

        # ── Walk animation ────────────────────────────────────────────────────
        if self.on_ground and abs(self.vx) > 0.5:
            self.walk_timer += 1
            if self.walk_timer >= 8:
                self.walk_timer = 0
                self.walk_frame = (self.walk_frame + 1) % 4
                if self.walk_frame in (0, 2):   # every other step
                    self.ev_step = True
        elif self.on_ground:
            self.walk_frame = 0

        # ── Death ─────────────────────────────────────────────────────────────
        if self.y > SCREEN_H + 100:
            self.alive = False
            self.ev_die = True

    # ── Sprite management ─────────────────────────────────────────────────────

    def _ensure_sprites(self):
        """
        Build all animation frames on the first draw call.
        Must be called after pygame.display.set_mode() exists (SRCALPHA needs it).

        Frames:
          idle        – standing still, weight slightly forward
          walk0–walk3 – four-frame walk cycle (legs/arms at 0°, 90°, 180°, 270°)
          jump        – airborne pose with tucked legs and raised arms
        """
        if self._sprites is not None:
            return

        self._sprites = {}
        frame_defs = [
            # (name,   walk_angle,        airborne)
            ('idle',   0.0,               False),
            ('walk0',  0.0,               False),
            ('walk1',  math.pi / 2,       False),
            ('walk2',  math.pi,           False),
            ('walk3',  3 * math.pi / 2,   False),
            ('jump',   math.pi / 4,       True ),
        ]

        for name, angle, airborne in frame_defs:
            for facing in (True, False):
                surf = pygame.Surface((_SW, _SH), pygame.SRCALPHA)
                _draw_frame(surf, _SAX, _SAY, facing, angle, airborne)
                self._sprites[(name, facing)] = surf

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surface, cam_x):
        """Blit the correct sprite frame so the foot-point lands at world pos x,y."""
        if not self.alive:
            return
        self._ensure_sprites()

        # Select animation state
        if not self.on_ground:
            frame_name = 'jump'
        elif abs(self.vx) > 0.5:
            frame_name = f'walk{self.walk_frame}'
        else:
            frame_name = 'idle'

        sprite = self._sprites[(frame_name, self.facing_right)]
        blit_x = int(self.x - cam_x) - _SAX
        blit_y = int(self.y)         - _SAY
        surface.blit(sprite, (blit_x, blit_y))

    # ── Legacy direct-draw (kept for UI / debug use) ──────────────────────────

    def _draw_at(self, surface, sx, sy, color=WHITE, lw=_LW):
        """Draw the character at foot position (sx, sy) directly onto *surface*."""
        tmp = pygame.Surface((_SW, _SH), pygame.SRCALPHA)
        _draw_frame(tmp, _SAX, _SAY, self.facing_right,
                    self.walk_frame * math.pi / 2,
                    airborne=not self.on_ground)
        surface.blit(tmp, (sx - _SAX, sy - _SAY))

"""
character.py – Mr. Linea player character.

MrLinea handles physics, collision, animation, and drawing.
Call char.update(...) once per frame; read sound-event flags
(ev_jump, ev_land, ev_step, ev_star, ev_die) each frame then clear them.

Drawing uses PNG sprites from sprites/ :
  fighter_walk_0009–0016  (8 frames) – normal walk
  fighter_run_0017–0024   (8 frames) – run (hold Shift)
Sprites are pre-loaded and cached; left-facing versions are pre-flipped.
"""

import os
import pygame

from constants import SCREEN_H, GRAVITY, JUMP_FORCE, MOVE_SPEED

# ── Sprite-sheet constants ────────────────────────────────────────────────────
_SPRITE_DIR = os.path.join(os.path.dirname(__file__), 'sprites')

# Scale 512×512 source images down so the character is ~54 px tall (= CHAR_H).
# In the source images the character occupies roughly y=207–380, height≈173 px.
# 54/173 ≈ 0.312  →  512 * 0.312 ≈ 160 px scaled surface.
_SCALE  = 0.3125          # 512 → 160 px
_SURF_W = 160
_SURF_H = 160

# Foot-anchor within the scaled surface.
# In original pixels: character x-centre ≈ 269, bottom ≈ 380.
# 269 * 0.3125 ≈ 84 ;  380 * 0.3125 ≈ 119
_FOOT_X = 84
_FOOT_Y = 119

# Animation file lists
_WALK_FILES = [f'fighter_walk_{i:04d}.png' for i in range(9, 17)]   # 8 frames
_RUN_FILES  = [f'fighter_run_{i:04d}.png'  for i in range(17, 25)]  # 8 frames

# Run speed multiplier (hold Shift)
RUN_SPEED = MOVE_SPEED * 1.8


# ── Character class ───────────────────────────────────────────────────────────

class MrLinea:
    """Profile sprite character with physics, collision, and animation."""

    CHAR_H = 54   # feet-to-crown height (collision geometry)
    CHAR_W = 14   # half-width for wall collisions

    def __init__(self, x, y):
        self.x  = float(x)   # feet x
        self.y  = float(y)   # feet y
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground       = False
        self.facing_right    = True
        self.running         = False
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

        # Determine run/walk
        shift = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        speed = RUN_SPEED if shift else MOVE_SPEED

        # Horizontal input
        moving = False
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.vx = speed
            self.facing_right = True
            self.running = shift
            moving = True
        elif keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.vx = -speed * 0.75
            self.facing_right = False
            self.running = shift
            moving = True
        else:
            self.vx *= 0.82   # friction
            self.running = False

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
        self.on_ground = False
        best_gy   = float('inf')
        best_line = None

        for seg in segments:
            margin = 4
            if not (seg.contains_x(self.x) or seg.contains_x(self.x - margin) or seg.contains_x(self.x + margin)):
                continue
            cx  = max(seg.x1, min(seg.x2, self.x))
            gy  = seg.y_at(cx)

            swept  = prev_y <= gy + 1 and self.y >= gy - 1
            follow = was_on_ground and (self.y - gy) <= 20 and (gy - self.y) <= 10

            if (swept or follow) and self.vy >= 0:
                if gy < best_gy:
                    best_gy   = gy
                    best_line = seg

        if best_line is not None and self.vy >= 0:
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
            char_left  = self.x - self.CHAR_W
            char_right = self.x + self.CHAR_W
            char_top   = self.y - self.CHAR_H
            char_bot   = self.y

            wall_left  = wx
            wall_right = wx + ww
            wall_top   = wy
            wall_bot   = wy + wh

            if char_right > wall_left and char_left < wall_right and char_bot > wall_top and char_top < wall_bot:
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
            # Advance faster when running
            tick_rate = 5 if self.running else 8
            self.walk_timer += 1
            if self.walk_timer >= tick_rate:
                self.walk_timer = 0
                self.walk_frame = (self.walk_frame + 1) % 8
                if self.walk_frame in (0, 2, 4, 6):   # every other step
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
        Load and scale all animation sprites on the first draw call.
        Must be called after pygame.display.set_mode() (convert_alpha needs it).

        Cache layout:  _sprites[(anim, facing_right)] = list of Surfaces
          anim ∈ {'walk', 'run'}
          facing_right ∈ {True, False}
        """
        if self._sprites is not None:
            return

        self._sprites = {}

        def load_strip(filenames):
            frames_r, frames_l = [], []
            for fname in filenames:
                raw = pygame.image.load(
                    os.path.join(_SPRITE_DIR, fname)
                ).convert_alpha()
                scaled = pygame.transform.scale(raw, (_SURF_W, _SURF_H))
                frames_r.append(scaled)
                frames_l.append(pygame.transform.flip(scaled, True, False))
            return frames_r, frames_l

        walk_r, walk_l = load_strip(_WALK_FILES)
        run_r,  run_l  = load_strip(_RUN_FILES)

        self._sprites[('walk', True)]  = walk_r
        self._sprites[('walk', False)] = walk_l
        self._sprites[('run',  True)]  = run_r
        self._sprites[('run',  False)] = run_l

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surface, cam_x):
        """Blit the correct sprite frame so the foot-point lands at world pos (x, y)."""
        if not self.alive:
            return
        self._ensure_sprites()

        # Choose animation set
        if self.on_ground and self.running and abs(self.vx) > 0.5:
            anim = 'run'
        else:
            anim = 'walk'

        frames = self._sprites[(anim, self.facing_right)]

        if abs(self.vx) > 0.5 or not self.on_ground:
            frame_idx = self.walk_frame % len(frames)
        else:
            frame_idx = 0

        sprite = frames[frame_idx]
        blit_x = int(self.x - cam_x) - _FOOT_X
        blit_y = int(self.y)         - _FOOT_Y
        surface.blit(sprite, (blit_x, blit_y))

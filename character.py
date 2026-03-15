"""
character.py – Mr. Linea player character.

MrLinea handles physics, collision, animation, and drawing.
Call char.update(...) once per frame; read sound-event flags
(ev_jump, ev_land, ev_step, ev_star, ev_die) each frame then clear them.

Drawing uses PNG sprites from sprites/ :
  fighter_walk_0009–0016  (8 frames) – normal walk
  fighter_run_0017–0024   (8 frames) – run (hold Shift)

gravity_flipped=True puts the character on the underside of the line:
  - gravity pulls upward, jump pushes downward
  - collision attaches from below
  - sprites are pre-cached with all four facing × gravity combinations
"""

import os
import pygame

from constants import SCREEN_H, GRAVITY, JUMP_FORCE, MOVE_SPEED

# ── Sprite-sheet constants ────────────────────────────────────────────────────
_SPRITE_DIR = os.path.join(os.path.dirname(str(__file__)), 'sprites')

# Scale 512×512 source images so the character is ~54 px tall (= CHAR_H).
_SCALE  = 0.3125          # 512 → 160 px
_SURF_W = 160
_SURF_H = 160

# Foot-anchor within the scaled surface (right-facing, normal gravity).
# In original pixels: character x-centre ≈ 269, bottom ≈ 380.
_FOOT_X = 84    # 269 * 0.3125 ≈ 84
_FOOT_Y = 119   # 380 * 0.3125 ≈ 119

# When gravity is flipped, the sprite is flipped vertically.
# The foot (originally at _FOOT_Y from top) moves to _SURF_H - _FOOT_Y from top.
_FOOT_Y_FLIP = _SURF_H - _FOOT_Y   # = 41

_WALK_FILES = [f'fighter_walk_{i:04d}.png' for i in range(9,  17)]   # 8 frames
_RUN_FILES  = [f'fighter_run_{i:04d}.png'  for i in range(17, 25)]  # 8 frames
_IDLE_FILES = [f'fighter_Idle_{i:04d}.png' for i in range(1,   9)]  # 8 frames
_JUMP_FILES = [f'fighter_jump_{i:04d}.png' for i in range(43, 48)]  # 5 frames

RUN_SPEED = MOVE_SPEED * 1.8


# ── Character class ───────────────────────────────────────────────────────────

class MrLinea:
    """Profile sprite character with physics, collision, and animation."""

    CHAR_H = 54   # feet-to-crown height (collision geometry)
    CHAR_W = 14   # half-width for wall collisions

    def __init__(self, x, y):
        self.x  = float(x)   # contact-point x  (feet / top-of-head)
        self.y  = float(y)   # contact-point y  (feet when normal, top when flipped)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground       = False
        self.facing_right    = True
        self.running         = False
        self.gravity_flipped = False
        self.walk_timer      = 0
        self.walk_frame      = 0
        self.idle_timer      = 0
        self.idle_frame      = 0
        self.alive           = True
        self.lives           = 3
        self.invincible_timer = 0
        self.stars_collected = 0
        # Sound-event flags – read by main loop each frame, then cleared
        self.ev_jump = False
        self.ev_land = False
        self.ev_step = False
        self.ev_star = False
        self.ev_die  = False
        self.ev_hit  = False
        # Sprite cache – populated lazily on first draw (needs display surface)
        self._sprites = None

    # ── Physics & collision ───────────────────────────────────────────────────

    def update(self, segments, walls, keys, stars_list):
        if not self.alive:
            return

        grav_sign = -1 if self.gravity_flipped else 1   # +1 = down, -1 = up

        # Determine run/walk
        shift = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        speed = RUN_SPEED if shift else MOVE_SPEED

        # Horizontal input (controls unchanged regardless of gravity direction)
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
            self.vx *= 0.82
            self.running = False

        # Jump (away from line, direction depends on gravity)
        if (keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]) and self.on_ground:
            self.vy = JUMP_FORCE * grav_sign   # JUMP_FORCE=-13.5; flipped → +13.5
            self.on_ground = False
            self.ev_jump = True

        was_on_ground = self.on_ground

        # Gravity (pulls toward whichever side the line is on)
        self.vy += GRAVITY * grav_sign

        prev_y = self.y

        # Integrate
        self.x += self.vx
        self.y += self.vy

        # ── Terrain collision ─────────────────────────────────────────────────
        self.on_ground = False

        if not self.gravity_flipped:
            # Normal: land on TOP of line (char.y moves down to meet gy)
            best_gy   = float('inf')
            best_line = None
            for seg in segments:
                margin = 4
                if not (seg.contains_x(self.x) or seg.contains_x(self.x - margin) or seg.contains_x(self.x + margin)):
                    continue
                cx = max(seg.x1, min(seg.x2, self.x))
                gy = seg.y_at(cx)
                swept  = prev_y <= gy + 1 and self.y >= gy - 1
                follow = was_on_ground and (self.y - gy) <= 20 and (gy - self.y) <= 10
                if (swept or follow) and self.vy >= 0:
                    if gy < best_gy:
                        best_gy = gy; best_line = seg
            if best_line is not None and self.vy >= 0:
                force = self.vy * 0.30 + 0.40
                best_line.apply_force(self.x, force)
                self.y  = best_gy
                self.vy = 0.0
                self.on_ground = True
                if not was_on_ground:
                    self.ev_land = True
        else:
            # Flipped: attach to UNDERSIDE of line (char.y moves up to meet gy)
            best_gy   = float('-inf')
            best_line = None
            for seg in segments:
                margin = 4
                if not (seg.contains_x(self.x) or seg.contains_x(self.x - margin) or seg.contains_x(self.x + margin)):
                    continue
                cx = max(seg.x1, min(seg.x2, self.x))
                gy = seg.y_at(cx)
                swept  = prev_y >= gy - 1 and self.y <= gy + 1
                follow = was_on_ground and (gy - self.y) <= 20 and (self.y - gy) <= 10
                if (swept or follow) and self.vy <= 0:
                    if gy > best_gy:
                        best_gy = gy; best_line = seg
            if best_line is not None and self.vy <= 0:
                force = abs(self.vy) * 0.30 + 0.40
                best_line.apply_force(self.x, -force)   # push upward
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
            if self.gravity_flipped:
                char_top = self.y               # contact at top when flipped
                char_bot = self.y + self.CHAR_H
            else:
                char_top = self.y - self.CHAR_H
                char_bot = self.y               # contact at bottom normally

            wall_right = wx + ww
            wall_bot   = wy + wh

            if char_right > wx and char_left < wall_right and char_bot > wy and char_top < wall_bot:
                overlap_r = char_right - wx
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
            if abs(self.x - sx) < 24 and abs(self.y - sy) < 60:
                stars_list.remove(star)
                self.stars_collected += 1
                self.ev_star = True

        # ── Walk / idle animation ─────────────────────────────────────────────
        if self.on_ground and abs(self.vx) > 0.5:
            tick_rate = 5 if self.running else 8
            self.walk_timer += 1
            if self.walk_timer >= tick_rate:
                self.walk_timer = 0
                self.walk_frame = (self.walk_frame + 1) % 8
                if self.walk_frame in (0, 2, 4, 6):
                    self.ev_step = True
            self.idle_timer = 0
            self.idle_frame = 0
        elif self.on_ground:
            self.walk_frame  = 0
            self.idle_timer += 1
            if self.idle_timer >= 10:
                self.idle_timer = 0
                self.idle_frame = (self.idle_frame + 1) % 8

        # ── Invincibility countdown ───────────────────────────────────────────
        if self.invincible_timer > 0:
            self.invincible_timer -= 1

        # ── Death ─────────────────────────────────────────────────────────────
        if self.y > SCREEN_H + 100 or self.y < -100:
            self.lives = 0
            self.alive = False
            self.ev_die = True

    def take_damage(self):
        """Called by the main loop when an enemy hits the player."""
        if self.invincible_timer > 0:
            return
        self.lives -= 1
        self.ev_hit = True
        if self.lives <= 0:
            self.alive   = False
            self.ev_die  = True
        else:
            self.invincible_timer = 100   # ~1.7 s of invincibility

    # ── Sprite management ─────────────────────────────────────────────────────

    def _ensure_sprites(self):
        """
        Load and scale all animation sprites on the first draw call.
        Must be called after pygame.display.set_mode() (convert_alpha needs it).

        Cache key: (anim, facing_right, gravity_flipped)
          anim            ∈ {'walk', 'run'}
          facing_right    ∈ {True, False}
          gravity_flipped ∈ {True, False}
        """
        if self._sprites is not None:
            return

        self._sprites = {}

        def load_strip(filenames):
            """Returns (right_normal, left_normal, right_flipped, left_flipped)."""
            rn, ln, rf, lf = [], [], [], []
            for fname in filenames:
                raw = pygame.image.load(
                    str(os.path.join(_SPRITE_DIR, fname))
                ).convert_alpha()
                scaled = pygame.transform.scale(raw, (_SURF_W, _SURF_H))
                rn.append(scaled)
                ln.append(pygame.transform.flip(scaled, True,  False))
                rf.append(pygame.transform.flip(scaled, False, True ))
                lf.append(pygame.transform.flip(scaled, True,  True ))
            return rn, ln, rf, lf

        for anim, files in (('walk', _WALK_FILES), ('run', _RUN_FILES),
                             ('idle', _IDLE_FILES), ('jump', _JUMP_FILES)):
            rn, ln, rf, lf = load_strip(files)
            self._sprites[(anim, True,  False)] = rn
            self._sprites[(anim, False, False)] = ln
            self._sprites[(anim, True,  True)]  = rf
            self._sprites[(anim, False, True)]  = lf

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surface, cam_x):
        """Blit the correct sprite frame so the contact-point lands at world pos (x, y)."""
        if not self.alive:
            return
        # Flash every 6 frames while invincible
        if self.invincible_timer > 0 and (self.invincible_timer // 6) % 2 == 0:
            return
        self._ensure_sprites()

        # Choose animation set and frame index
        if not self.on_ground:
            # Jump frame driven by vertical velocity: 0 = takeoff … 4 = falling fast
            vy = self.vy * (-1 if self.gravity_flipped else 1)  # normalise upward = negative
            if   vy < -8: frame_idx = 0
            elif vy < -3: frame_idx = 1
            elif vy <  2: frame_idx = 2
            elif vy <  7: frame_idx = 3
            else:         frame_idx = 4
            anim = 'jump'
        elif abs(self.vx) > 0.5:
            anim      = 'run' if self.running else 'walk'
            frame_idx = self.walk_frame % 8
        else:
            anim      = 'idle'
            frame_idx = self.idle_frame

        frames = self._sprites[(anim, self.facing_right, self.gravity_flipped)]

        sprite = frames[frame_idx]
        blit_x = int(self.x - cam_x) - _FOOT_X
        # Gravity-flipped sprites have the foot anchor at _FOOT_Y_FLIP from top
        foot_y = _FOOT_Y_FLIP if self.gravity_flipped else _FOOT_Y
        blit_y = int(self.y) - foot_y
        surface.blit(sprite, (blit_x, blit_y))

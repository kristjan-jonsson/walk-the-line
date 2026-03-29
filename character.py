"""
character.py - player character.

Character handles physics, collision, animation, and drawing.
Call char.update(...) once per frame; read char.events (a set of strings)
and clear it: char.events.clear(). Event names: 'jump', 'land', 'step',
'star', 'hit', 'die'.

Drawing uses SVG sprites from sprites/chalkman/ :
  chalkman/walk/chalkman_walk1–8   (8 frames) - normal walk
  chalkman/run/chalkman_run1-8     (8 frames) - run (hold Shift)
  chalkman/idle/chalkman_idle1-8   (8 frames) - idle
  chalkman/jump/chalkman_jump1-8   (8 frames) - jump

gravity_flipped=True puts the character on the underside of the line:
  - gravity pulls upward, jump pushes downward
  - collision attaches from below
  - sprites are pre-cached with all four facing x gravity combinations
"""

import os
import pygame

from constants import (SCREEN_H, GRAVITY, JUMP_FORCE, MOVE_SPEED,
                       RUN_SPEED_MULT, COLLISION_MARGIN,
                       GROUND_FOLLOW_DOWN, GROUND_FOLLOW_UP,
                       SPRING_FORCE_MULT, SPRING_FORCE_BASE,
                       INVINCIBLE_FRAMES, STAR_COLLECT_RX, STAR_COLLECT_RY)

# ── Sprite-sheet constants ────────────────────────────────────────────────────
_SPRITE_DIR = os.path.join(os.path.dirname(str(__file__)), 'sprites', 'chalkman')

# Scale 256×256 source images so the character is ~69 px tall (content height at this scale).
_SURF_W = 72
_SURF_H = 72

# Foot-anchor within the scaled surface (right-facing, normal gravity).
# Chalkman sprites are 256×256; feet are at y=255 (very bottom), centre-x ≈ 123.
_FOOT_X = 35    # 123 * (72/256) ≈ 35  (horizontal centre of feet)
_FOOT_Y = 71    # 255 * (72/256) ≈ 71  (feet at bottom of sprite)

# When gravity is flipped, the sprite is flipped vertically.
# The foot (originally at _FOOT_Y from top) moves to _SURF_H - _FOOT_Y from top.
_FOOT_Y_FLIP = _SURF_H - _FOOT_Y   # = 1

_WALK_FILES = [f'walk/chalkman_walk{i}.png' for i in range(1, 9)]   # 8 frames (PNG: SVGs used xlink:href unsupported by NanoSVG)
_RUN_FILES  = [f'run/chalkman_run{i}.svg'   for i in range(1, 9)]   # 8 frames
_IDLE_FILES = [f'idle/chalkman_idle{i}.svg' for i in range(1, 9)]   # 8 frames
_JUMP_FILES = [f'jump/chalkman_jump{i}.svg' for i in range(1, 9)]   # 8 frames

RUN_SPEED = MOVE_SPEED * RUN_SPEED_MULT


# ── Character class ───────────────────────────────────────────────────────────

class Character:
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
        # Event set - populated during update(), consumed and cleared by main loop
        self.events: set = set()
        # Sprite cache - populated lazily on first draw (needs display surface)
        self._sprites = None

    # ── Public methods ────────────────────────────────────────────────────────

    def flip_gravity(self):
        """Reverse gravity direction and detach so physics re-attaches to new side."""
        self.gravity_flipped = not self.gravity_flipped
        self.on_ground = False

    def take_damage(self):
        """Called when an enemy hits the player."""
        if self.invincible_timer > 0:
            return
        self.lives -= 1
        self.events.add('hit')
        if self.lives <= 0:
            self.alive  = False
            self.events.add('die')
        else:
            self.invincible_timer = INVINCIBLE_FRAMES

    # ── Physics & collision ───────────────────────────────────────────────────

    def update(self, segments, walls, keys, stars_list):
        if not self.alive:
            return
        grav_sign     = -1 if self.gravity_flipped else 1
        was_on_ground = self.on_ground
        self._handle_input(keys, grav_sign)
        prev_y = self._apply_physics(grav_sign)
        self._resolve_terrain_collision(segments, prev_y, was_on_ground, grav_sign)
        self._handle_wall_collision(walls)
        self._collect_stars(stars_list)
        self._update_animation()
        if self.invincible_timer > 0:
            self.invincible_timer -= 1
        if self.y > SCREEN_H + 100 or self.y < -100:
            self.lives = 0
            self.alive = False
            self.events.add('die')

    def _handle_input(self, keys, grav_sign):
        shift = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        speed = RUN_SPEED if shift else MOVE_SPEED
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.vx = speed
            self.facing_right = True
            self.running = shift
        elif keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.vx = -speed * 0.75
            self.facing_right = False
            self.running = shift
        else:
            self.vx *= 0.82
            self.running = False
        if (keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]) and self.on_ground:
            self.vy = JUMP_FORCE * grav_sign   # JUMP_FORCE=-13.5; flipped → +13.5
            self.on_ground = False
            self.events.add('jump')

    def _apply_physics(self, grav_sign):
        """Apply gravity and integrate position. Returns prev_y before integration."""
        self.vy += GRAVITY * grav_sign
        prev_y  = self.y
        self.x += self.vx
        self.y += self.vy
        self.on_ground = False
        return prev_y

    def _resolve_terrain_collision(self, segments, prev_y, was_on_ground, grav_sign):
        """Unified terrain collision for both normal and flipped gravity.

        grav_sign = +1: land on top of line (standard).
        grav_sign = -1: attach to underside of line (flipped).
        """
        best_gy   = grav_sign * float('inf')   # +inf (normal) / -inf (flipped)
        best_line = None
        for seg in segments:
            if not (seg.contains_x(self.x)
                    or seg.contains_x(self.x - COLLISION_MARGIN)
                    or seg.contains_x(self.x + COLLISION_MARGIN)):
                continue
            cx = max(seg.x1, min(seg.x2, self.x))
            gy = seg.y_at(cx)
            # swept: was on one side of line, now on the other (or at it)
            swept  = (grav_sign * (prev_y - gy) <= 1
                      and grav_sign * (self.y - gy) >= -1)
            # follow: already grounded and still close enough to the line
            follow = (was_on_ground
                      and grav_sign * (self.y - gy) <= GROUND_FOLLOW_DOWN
                      and grav_sign * (gy - self.y) <= GROUND_FOLLOW_UP)
            if (swept or follow) and self.vy * grav_sign >= 0:
                if grav_sign * gy < grav_sign * best_gy:
                    best_gy, best_line = gy, seg
        if best_line is not None and self.vy * grav_sign >= 0:
            force = abs(self.vy) * SPRING_FORCE_MULT + SPRING_FORCE_BASE
            best_line.apply_force(self.x, grav_sign * force)
            self.y  = best_gy
            self.vy = 0.0
            self.on_ground = True
            if not was_on_ground:
                self.events.add('land')

    def _handle_wall_collision(self, walls):
        for wall in walls:
            wx, wy, ww, wh = wall
            char_left  = self.x - self.CHAR_W
            char_right = self.x + self.CHAR_W
            if self.gravity_flipped:
                char_top = self.y
                char_bot = self.y + self.CHAR_H
            else:
                char_top = self.y - self.CHAR_H
                char_bot = self.y
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

    def _collect_stars(self, stars_list):
        for star in stars_list[:]:
            sx, sy = star
            if abs(self.x - sx) < STAR_COLLECT_RX and abs(self.y - sy) < STAR_COLLECT_RY:
                stars_list.remove(star)
                self.stars_collected += 1
                self.events.add('star')

    def _update_animation(self):
        if self.on_ground and abs(self.vx) > 0.5:
            tick_rate = 5 if self.running else 8
            self.walk_timer += 1
            if self.walk_timer >= tick_rate:
                self.walk_timer = 0
                self.walk_frame = (self.walk_frame + 1) % 8
                if self.walk_frame in (0, 2, 4, 6):
                    self.events.add('step')
            self.idle_timer = 0
            self.idle_frame = 0
        elif self.on_ground:
            self.walk_frame  = 0
            self.idle_timer += 1
            if self.idle_timer >= 10:
                self.idle_timer = 0
                self.idle_frame = (self.idle_frame + 1) % 8

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

"""
Walk the Line - A minimalist endless platformer.

The character walks along a single white line that forms their entire world.
Jump over gaps and obstacles to reach the end!

Controls:
  Arrow Right / D  - Walk right
  Arrow Left  / A  - Walk left
  Space / Up  / W  - Jump
  Shift           - Run
  R               - Restart
  Escape          - Quit
"""

import asyncio
import os
import pygame
import math
import random
import array

from constants   import SCREEN_W, SCREEN_H, FPS, JUMP_FORCE
from spring_line import SpringLine
from level       import LevelGenerator
from character   import Character
from clouds      import CloudSystem
from enemies     import Enemy, draw_hearts
import highscore as hs

pygame.mixer.pre_init(44100, -16, 2, 2048)
pygame.init()
pygame.mixer.set_num_channels(8)

# Palette – minimalist like the show
WHITE       = (255, 255, 255)
BLACK       = (0,   0,   0)
STAR_COLOR  = (255, 240, 80)
PARTICLE_C  = (255, 255, 255)



# ─────────────────────────────────────────────────────────────────────────────
# Sound engine  (all audio generated procedurally – no files needed)
# ─────────────────────────────────────────────────────────────────────────────

class SoundEngine:
    SR   = 44100          # sample rate (must match pre_init above)
    # Sine lookup table – much faster than math.sin() in a tight loop
    _N   = 4096
    _LUT = [math.sin(2 * math.pi * i / 4096) for i in range(4096)]

    # ── helpers ───────────────────────────────────────────────────────────

    @classmethod
    def _sin(cls, phase):
        """phase in [0, 1) → sine value via LUT."""
        return cls._LUT[int(phase * cls._N) & (cls._N - 1)]

    @classmethod
    def _pack(cls, samples):
        """float list [-1,1] → pygame.mixer.Sound (16-bit mono)."""
        ints = array.array('h',
            (max(-32768, min(32767, int(s * 32767))) for s in samples))
        return pygame.mixer.Sound(buffer=ints)

    # ── individual sound builders ─────────────────────────────────────────

    # @classmethod
    # def _footstep(cls):
    #     """Soft papery tap."""
    #     n = int(cls.SR * 0.035)
    #     rng = random.Random(42)
    #     return cls._pack(
    #         (rng.uniform(-1, 1) * max(0, 1 - i / n) ** 2 * 0.18
    #          for i in range(n)))

    # @classmethod
    # def _jump(cls):
    #     """Quick upward frequency sweep – boing."""
    #     dur, sr = 0.17, cls.SR
    #     n = int(sr * dur)
    #     s = cls._sin
    #     samples = []
    #     phase = 0.0
    #     for i in range(n):
    #         t   = i / sr
    #         env = max(0.0, 1.0 - t / dur) ** 0.6
    #         freq = 180 + 900 * (t / dur) ** 0.45
    #         samples.append(s(phase) * env * 0.42)
    #         phase = (phase + freq / sr) % 1.0
    #     return cls._pack(samples)

    @classmethod
    def _land(cls):
        """Low thud on landing."""
        dur, sr = 0.11, cls.SR
        n = int(sr * dur)
        s = cls._sin
        samples = []
        phase = 0.0
        for i in range(n):
            t   = i / sr
            env = max(0.0, 1.0 - (t / dur) ** 0.5)
            freq = 95 - 40 * (t / dur)
            samples.append(s(phase) * env * 0.45)
            phase = (phase + freq / sr) % 1.0
        return cls._pack(samples)

    @classmethod
    def _star_ding(cls):
        """Bright C-E-G chord chime."""
        dur, sr = 0.28, cls.SR
        n   = int(sr * dur)
        s   = cls._sin
        freqs  = [523.25, 659.25, 783.99]          # C5, E5, G5
        phases = [0.0] * 3
        samples = []
        for i in range(n):
            t   = i / sr
            env = max(0.0, 1.0 - t / dur) ** 1.8
            val = sum(s(phases[k]) for k in range(3)) / 3 * env * 0.38
            samples.append(val)
            for k in range(3):
                phases[k] = (phases[k] + freqs[k] / sr) % 1.0
        return cls._pack(samples)

    @classmethod
    def _hit(cls):
        """Short sharp thwack — player takes damage."""
        dur, sr = 0.09, cls.SR
        n = int(sr * dur)
        s = cls._sin
        samples = []
        phase = 0.0
        for i in range(n):
            t   = i / sr
            env = max(0.0, 1.0 - (t / dur) ** 0.4)
            freq = 180 - 90 * (t / dur)
            samples.append(s(phase) * env * 0.55)
            phase = (phase + freq / sr) % 1.0
        return cls._pack(samples)

    @classmethod
    def _die(cls):
        """Sad descending glide."""
        dur, sr = 0.55, cls.SR
        n = int(sr * dur)
        s = cls._sin
        samples = []
        phase = 0.0
        for i in range(n):
            t    = i / sr
            env  = max(0.0, 1.0 - t / dur)
            freq = 420 * (1.0 - 0.68 * (t / dur))
            samples.append(s(phase) * env * 0.42)
            phase = (phase + freq / sr) % 1.0
        return cls._pack(samples)

    @classmethod
    def _win(cls):
        """Short ascending C-E-G-C5 fanfare."""
        sr    = cls.SR
        notes = [(261.63, 0.13), (329.63, 0.13), (392.00, 0.13), (523.25, 0.42)]
        samples = []
        s = cls._sin
        for freq, dur in notes:
            n, phase = int(sr * dur), 0.0
            for i in range(n):
                t   = i / sr
                env = min(t * 60, 1.0) * max(0.0, 1.0 - (t / dur) ** 2)
                samples.append(s(phase) * env * 0.42)
                phase = (phase + freq / sr) % 1.0
        return cls._pack(samples)

    # ── public API ────────────────────────────────────────────────────────

    def __init__(self):
        # self.snd_footstep = self._footstep()
        # self.snd_jump     = self._jump()
        self.snd_land     = self._land()
        self.snd_star     = self._star_ding()
        self.snd_hit      = self._hit()
        self.snd_die      = self._die()
        self.snd_win      = self._win()
        pygame.mixer.music.load(os.path.join("sound", "background-music.ogg"))

    def start_music(self):
        pygame.mixer.music.set_volume(0.55)
        pygame.mixer.music.play(loops=-1)

    def stop_music(self):
        pygame.mixer.music.stop()

    def play(self, snd, vol=1.0):
        ch = snd.play()
        if ch:
            ch.set_volume(vol)



# ─────────────────────────────────────────────────────────────────────────────
# Drawing helpers
# ─────────────────────────────────────────────────────────────────────────────

def draw_terrain(surface, segments, walls, cam_x):
    sorted_segs = sorted(segments, key=lambda s: s.x1)
    for idx, seg in enumerate(sorted_segs):
        if seg.x2 - cam_x < -50 or seg.x1 - cam_x > SCREEN_W + 50:
            continue
        # Connect every adjacent pair of spring nodes — one continuous chain
        for i in range(len(seg.nx) - 1):
            ax = int(seg.nx[i]     - cam_x)
            bx = int(seg.nx[i + 1] - cam_x)
            if bx < -4 or ax > SCREEN_W + 4:
                continue
            pygame.draw.line(surface, WHITE,
                             (ax, int(seg.y[i])),
                             (bx, int(seg.y[i + 1])), 4)
        # Draw connector to the next segment when they share a junction (no gap).
        if idx + 1 < len(sorted_segs):
            nxt = sorted_segs[idx + 1]
            if nxt.x1 - seg.x2 < 2:   # adjacent, not a gap
                ax = int(seg.nx[-1]  - cam_x)
                bx = int(nxt.nx[0]   - cam_x)
                if -4 <= bx <= SCREEN_W + 4 or -4 <= ax <= SCREEN_W + 4:
                    pygame.draw.line(surface, WHITE,
                                     (ax, int(seg.y[-1])),
                                     (bx, int(nxt.y[0])), 4)

    for wall in walls:
        wx, wy, ww, wh = wall
        sx = wx - cam_x
        if sx + ww < -10 or sx > SCREEN_W + 10:
            continue
        r = pygame.Rect(int(sx), int(wy), int(ww), int(wh))
        pygame.draw.rect(surface, WHITE, r, 3)


def draw_stars(surface, stars, cam_x, t):
    for sx, sy in stars:
        screen_x = sx - cam_x
        if screen_x < -30 or screen_x > SCREEN_W + 30:
            continue
        # Pulsing star
        pulse = 1.0 + 0.2 * math.sin(t * 0.06 + sx * 0.05)
        r = int(10 * pulse)
        # Simple 4-pointed star shape
        cx, cy = int(screen_x), int(sy)
        pts = []
        for i in range(8):
            angle = math.pi / 4 * i
            radius = r if i % 2 == 0 else r // 2
            pts.append((cx + int(math.cos(angle) * radius),
                         cy + int(math.sin(angle) * radius)))
        pygame.draw.polygon(surface, WHITE, pts)
        pygame.draw.polygon(surface, WHITE, pts, 1)


def draw_hand_pencil(surface, x, y, alpha=255):
    """The cartoonist's hand — appears at death / win."""
    # Pencil body
    pts_pencil = [(x, y), (x + 10, y - 40), (x + 15, y - 40), (x + 5, y)]
    s = pygame.Surface((60, 60), pygame.SRCALPHA)
    pygame.draw.polygon(s, (255, 220, 140, alpha), [(p[0] - x + 5, p[1] - y + 45) for p in pts_pencil])
    pygame.draw.polygon(s, (255, 255, 255, alpha), [(p[0] - x + 5, p[1] - y + 45) for p in pts_pencil], 2)
    # Tip
    tip = [(x + 2, y), (x + 7, y - 10), (x + 13, y - 10), (x + 8, y)]
    pygame.draw.polygon(s, (120, 90, 60, alpha), [(p[0] - x + 5, p[1] - y + 45) for p in tip])
    surface.blit(s, (x - 5, y - 45))


def draw_flip_triggers(surface, flip_triggers, segments, cam_x, t):
    """Draw a pulsing ↕ portal marker at each upcoming gravity-flip trigger."""
    for tx in flip_triggers:
        sx = int(tx - cam_x)
        if sx < -20 or sx > SCREEN_W + 20:
            continue
        # Find terrain y at this x
        line_y = SCREEN_H // 2
        for seg in segments:
            if seg.contains_x(tx):
                line_y = int(seg.y_at(tx))
                break
        pulse = 0.5 + 0.5 * math.sin(t * 0.12)
        alpha = int(140 + 80 * pulse)
        col   = (alpha, alpha, alpha)
        # Dashed vertical stripe centred on the line
        for y in range(max(0, line_y - 80), min(SCREEN_H, line_y + 80), 12):
            if ((y - line_y) // 12) % 2 == 0:
                pygame.draw.line(surface, col, (sx, y), (sx, min(y + 6, SCREEN_H)), 2)
        # ↑ arrow above
        ay = line_y - 52
        pygame.draw.polygon(surface, col, [(sx, ay), (sx - 7, ay + 14), (sx + 7, ay + 14)], 2)
        # ↓ arrow below
        ay = line_y + 52
        pygame.draw.polygon(surface, col, [(sx, ay), (sx - 7, ay - 14), (sx + 7, ay - 14)], 2)



# ─────────────────────────────────────────────────────────────────────────────
# Game
# ─────────────────────────────────────────────────────────────────────────────

class Game:
    BG_PALETTE = [
        (65,  120, 185),   # sky blue
        (180, 100,  65),   # warm terracotta
        (60,  150,  80),   # meadow green
        (130,  70, 160),   # dusk violet
        (190, 160,  50),   # golden afternoon
    ]

    # Camera
    _CAMERA_LEAD   = 50      # px anticipation ahead in facing direction
    _CAMERA_SMOOTH = 0.10    # lerp factor per frame
    _CAMERA_OFFSET = 0.38    # x offset as fraction of screen width

    # Background
    _PALETTE_PERIOD = 2000   # px between colour changes

    # Particles
    _PARTICLE_GRAVITY = 0.35
    _PARTICLE_LIFE    = 55
    _PARTICLE_COUNT   = 28

    # Gameplay
    _STOMP_BOUNCE  = 0.6     # vy multiplier for stomp rebound
    _MUSIC_VOLUME  = 0.55
    _INTRO_FRAMES  = 60      # fade-in duration in frames

    # Level progression: (json path, stars needed to advance to next level)
    # The last entry has no threshold (None = play forever).
    _LEVEL_SEQUENCE = [
        ("levels/easy.json",    10),
        ("levels/default.json", 25),
        ("levels/hard.json",    None),
    ]

    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Walk the Line")
        self.clock      = pygame.time.Clock()
        self.sounds     = SoundEngine()
        self.sounds.start_music()
        self.font       = pygame.font.SysFont("Arial", 26)
        self.big_font   = pygame.font.SysFont("Arial", 68, bold=True)
        self.title_font = pygame.font.SysFont("Arial", 38, bold=True)
        self.music_muted  = False
        self.intro_done   = False
        self.intro_ticks  = self._INTRO_FRAMES
        self.best_score   = hs.load()   # metres – persisted across sessions
        self.new_record   = False
        self._reset()

    # ── setup / reset ────────────────────────────────────────────────────────

    def _reset(self):
        self._level_idx   = 0
        level_path        = self._LEVEL_SEQUENCE[0][0]
        self.gen          = LevelGenerator.from_file(level_path)
        self.char         = Character(60, self.gen.segments[0].y1)
        self.clouds       = CloudSystem()
        self.enemies      = []
        self.camera_x     = 0.0
        self.state        = "playing"   # playing | dead
        self.tick         = 0
        self.bg_color     = list(self.BG_PALETTE[0])
        self.particles    = []
        self.hand_alpha   = 0
        self.new_record   = False

    # ── level progression ────────────────────────────────────────────────────

    def _check_level_transition(self):
        """Advance to the next level when the star threshold is reached."""
        _, threshold = self._LEVEL_SEQUENCE[self._level_idx]
        if threshold is None:
            return   # final level – play forever
        if self.char.stars_collected >= threshold:
            self._level_idx += 1
            next_path, _ = self._LEVEL_SEQUENCE[self._level_idx]
            self._transition_level(next_path)

    def _transition_level(self, path):
        """Swap in a new LevelGenerator continuing from the end of existing terrain.
        Old segments/walls/stars still on screen are carried over seamlessly."""
        # Start new generation from the tip of existing terrain so no overlap occurs
        tip_seg = max(self.gen.segments, key=lambda s: s.x2)
        tip_x   = tip_seg.x2
        tip_y   = tip_seg.y2

        # Count pending flip triggers between player and tip_x to determine
        # the correct gravity state at the point where new generation starts.
        flips_ahead = sum(1 for fx in self.gen.flip_triggers
                          if self.char.x < fx <= tip_x)
        tip_gravity = self.char.gravity_flipped ^ (flips_ahead % 2 == 1)

        new_gen = LevelGenerator.from_file(path, start_x=tip_x, start_y=tip_y,
                                            gravity_flipped=tip_gravity)
        # Carry over everything already rendered; new gen provides what comes next
        new_gen.segments      = self.gen.segments      + new_gen.segments
        new_gen.walls         = self.gen.walls         + new_gen.walls
        new_gen.stars         = self.gen.stars         + new_gen.stars
        new_gen.flip_triggers = self.gen.flip_triggers + new_gen.flip_triggers
        self.gen     = new_gen
        self.enemies = []

    # ── event handling ───────────────────────────────────────────────────────

    def handle_events(self):
        """Process pygame events. Returns False when the game should quit."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key == pygame.K_r:
                    self._reset()
                    if not self.music_muted:
                        self.sounds.start_music()
                if event.key == pygame.K_m:
                    self.music_muted = not self.music_muted
                    pygame.mixer.music.set_volume(0.0 if self.music_muted else self._MUSIC_VOLUME)
        return True

    # ── update helpers ───────────────────────────────────────────────────────

    def _update_enemies(self):
        for ex, ey in self.gen.take_enemy_spawns():
            self.enemies.append(Enemy(ex, ey))
        for enemy in self.enemies:
            enemy.update(self.char.x, self.char.y, self.gen.segments)
        self.enemies = [e for e in self.enemies if e.x > self.char.x - self.gen.PRUNE_BEHIND]
        # Stomp (normal gravity only)
        if not self.char.gravity_flipped:
            for enemy in self.enemies:
                if enemy.stomped_by(self.char.x, self.char.y, self.char.vy):
                    enemy.alive = False
                    self.char.vy = JUMP_FORCE * self._STOMP_BOUNCE
        # Contact damage
        for enemy in self.enemies:
            if enemy.hits_player(self.char.x, self.char.y) and enemy.can_hit():
                self.char.take_damage()
                enemy.register_hit()

    def _handle_gravity_flips(self):
        pending = []
        for fx in self.gen.flip_triggers:
            if self.char.x > fx:
                self.char.flip_gravity()
            else:
                pending.append(fx)
        self.gen.flip_triggers = pending

    def _handle_sounds(self):
        events, snd = self.char.events, self.sounds
        # if 'jump' in events:  snd.play(snd.snd_jump,  0.7)
        if 'land' in events:  snd.play(snd.snd_land,  0.6)
        # if 'step' in events:  snd.play(snd.snd_footstep, 0.5)
        if 'star' in events:  snd.play(snd.snd_star,  0.9)
        if 'hit'  in events:  snd.play(snd.snd_hit,   0.8)
        if 'die'  in events:  snd.play(snd.snd_die,   0.8)
        self.char.events.clear()

    def _update_camera(self):
        lead     = self._CAMERA_LEAD if self.char.facing_right else -self._CAMERA_LEAD
        target_x = self.char.x - SCREEN_W * self._CAMERA_OFFSET + lead
        self.camera_x += (target_x - self.camera_x) * self._CAMERA_SMOOTH
        self.camera_x  = max(0.0, self.camera_x)

    def _update_particles(self):
        for p in self.particles:
            p["x"]  += p["vx"]
            p["y"]  += p["vy"]
            p["vy"] += self._PARTICLE_GRAVITY
            p["life"] -= 1
        self.particles = [p for p in self.particles if p["life"] > 0]

    def _spawn_death_particles(self):
        for _ in range(self._PARTICLE_COUNT):
            self.particles.append({
                "x":  self.char.x, "y": self.char.y - 20,
                "vx": random.uniform(-6, 6),
                "vy": random.uniform(-9, -1),
                "life": self._PARTICLE_LIFE,
            })

    # ── main update ──────────────────────────────────────────────────────────

    def update(self, keys):
        if self.state == "playing" and self.intro_done:
            self.gen.update(self.char.x)
            self.clouds.update(self.char.x, self.camera_x)
            for seg in self.gen.segments:
                seg.update()
            self.char.update(self.gen.segments, self.gen.walls, keys, self.gen.stars)
            self._update_enemies()
            self._handle_gravity_flips()
            self._handle_sounds()
            self._update_camera()

            pal_idx = int(self.char.x / self._PALETTE_PERIOD) % len(self.BG_PALETTE)
            self.bg_color = list(self.BG_PALETTE[pal_idx])

            if not self.char.alive:
                self.state = "dead"
                self.hand_alpha = 0
                self._spawn_death_particles()
                score = int(max(0, self.char.x - 60))
                if score > self.best_score:
                    self.best_score = score
                    self.new_record = True
                    hs.save(score)
            else:
                self._check_level_transition()

        self._update_particles()

        if self.state == "dead":
            self.hand_alpha = min(255, self.hand_alpha + 8)

    # ── draw helpers ─────────────────────────────────────────────────────────

    def _draw_hud(self):
        star_txt = self.font.render(f"★ {self.char.stars_collected}", True, STAR_COLOR)
        dist_txt = self.font.render(f"{int(max(0, self.char.x - 60))} m", True, WHITE)
        best_txt = self.font.render(f"Best: {self.best_score} m", True, (180, 220, 255))
        self.screen.blit(star_txt, (20, 20))
        draw_hearts(self.screen, self.char.lives)
        self.screen.blit(dist_txt, (SCREEN_W - dist_txt.get_width() - 20, 20))
        self.screen.blit(best_txt, (SCREEN_W - best_txt.get_width() - 20, 50))
        mute_txt = self.font.render("♪ M" if not self.music_muted else "✕ M", True,
                                    (180, 180, 180) if not self.music_muted else (220, 80, 80))
        self.screen.blit(mute_txt, (SCREEN_W - mute_txt.get_width() - 20, 80))
        if self.tick < 200:
            alpha = max(0, 255 - int(255 * (self.tick - 140) / 60)) if self.tick > 140 else 255
            hint  = self.font.render(
                "left/right Move    shift Sprint    space/up Jump    R Restart    M Mute",
                True, (alpha, alpha, alpha))
            self.screen.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, SCREEN_H - 38))

    def _draw_game_over(self):
        draw_hand_pencil(self.screen, SCREEN_W // 2 - 10, SCREEN_H // 2 - 80, self.hand_alpha)
        overlay = pygame.Surface((SCREEN_W, 160), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        self.screen.blit(overlay, (0, SCREEN_H // 2 - 20))
        msg = self.big_font.render("GAME OVER!", True, WHITE)
        self.screen.blit(msg, (SCREEN_W // 2 - msg.get_width() // 2, SCREEN_H // 2 - 10))
        score = int(max(0, self.char.x - 60))
        if self.new_record:
            rec_txt = self.font.render("★  NEW HIGH SCORE!  ★", True, STAR_COLOR)
            self.screen.blit(rec_txt, (SCREEN_W // 2 - rec_txt.get_width() // 2, SCREEN_H // 2 + 52))
            sub = self.font.render(
                f"{score} m  ★ {self.char.stars_collected}    Press R to try again",
                True, (220, 220, 220))
        else:
            sub = self.font.render(
                f"{score} m  ★ {self.char.stars_collected}    Best: {self.best_score} m    Press R to try again",
                True, (220, 220, 220))
        self.screen.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, SCREEN_H // 2 + 80))

    def _draw_intro(self):
        fade = pygame.Surface((SCREEN_W, SCREEN_H))
        fade.fill(BLACK)
        fade.set_alpha(int(255 * self.intro_ticks / self._INTRO_FRAMES))
        self.screen.blit(fade, (0, 0))
        title = self.title_font.render("Walk the Line", True, WHITE)
        self.screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, SCREEN_H // 2 - 20))

    # ── main draw ────────────────────────────────────────────────────────────

    def draw(self):
        cam = int(self.camera_x)
        self.screen.fill(tuple(int(c) for c in self.bg_color))
        self.clouds.draw(self.screen, self.camera_x, self.tick)
        draw_terrain(self.screen, self.gen.segments, self.gen.walls, cam)
        draw_flip_triggers(self.screen, self.gen.flip_triggers, self.gen.segments, cam, self.tick)
        draw_stars(self.screen, self.gen.stars, cam, self.tick)
        for enemy in self.enemies:
            enemy.draw(self.screen, cam)
        self.char.draw(self.screen, cam)
        for p in self.particles:
            alpha_f = p["life"] / self._PARTICLE_LIFE
            r = max(2, int(5 * alpha_f))
            pygame.draw.circle(self.screen, WHITE,
                               (int(p["x"] - self.camera_x), int(p["y"])), r)
        self._draw_hud()
        if self.state == "dead":
            self._draw_game_over()
        if not self.intro_done:
            self._draw_intro()
        pygame.display.flip()

    # ── game loop ────────────────────────────────────────────────────────────

    async def run(self):
        running = True
        while running:
            self.clock.tick(FPS)
            self.tick += 1
            if not self.intro_done:
                self.intro_ticks -= 1
                if self.intro_ticks <= 0:
                    self.intro_done = True
            keys    = pygame.key.get_pressed()
            running = self.handle_events()
            self.update(keys)
            self.draw()
            await asyncio.sleep(0)
        pygame.quit()


async def main():
    await Game().run()


if __name__ == "__main__":
    asyncio.run(main())

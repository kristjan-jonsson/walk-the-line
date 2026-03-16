"""
La Linea - A game inspired by the Italian animated TV series by Osvaldo Cavandoli.

Mr. Linea walks along a single white line that forms his entire world.
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
from character   import MrLinea
from clouds      import CloudSystem
from enemies     import Enemy, draw_hearts

pygame.mixer.pre_init(22050, -16, 1, 512)
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
    SR   = 22050          # sample rate (must match pre_init above)
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
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("La Linea")
    clock = pygame.time.Clock()

    sounds     = SoundEngine()
    sounds.start_music()

    font       = pygame.font.SysFont("Arial", 26)
    big_font   = pygame.font.SysFont("Arial", 68, bold=True)
    title_font = pygame.font.SysFont("Arial", 38, bold=True)

    # Background colour palette (shifts as you progress through the level)
    BG_PALETTE = [
        (65,  120, 185),   # sky blue
        (180, 100,  65),   # warm terracotta
        (60,  150,  80),   # meadow green
        (130,  70, 160),   # dusk violet
        (190, 160,  50),   # golden afternoon
    ]

    def new_game():
        gen    = LevelGenerator()
        char   = MrLinea(60, gen.segments[0].y1)
        clouds = CloudSystem()
        return gen, char, clouds, []   # enemies start empty

    gen, char, clouds, enemies = new_game()

    camera_x   = 0.0
    state      = "playing"    # playing | dead
    tick       = 0
    bg_color   = list(BG_PALETTE[0])
    particles  = []
    hand_alpha = 0
    music_muted = False

    # ── intro animation ───────────────────────────────────────────────────
    intro_ticks  = 60       # short pause before play
    intro_done   = False

    running = True
    while running:
        dt   = clock.tick(FPS)
        keys = pygame.key.get_pressed()
        tick += 1

        # ── events ────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_r:
                    gen, char, clouds, enemies = new_game()
                    camera_x   = 0.0
                    state      = "playing"
                    particles  = []
                    bg_color   = list(BG_PALETTE[0])
                    hand_alpha = 0
                    tick       = 0
                    if not music_muted:
                        sounds.start_music()
                if event.key == pygame.K_m:
                    music_muted = not music_muted
                    if music_muted:
                        pygame.mixer.music.set_volume(0.0)
                    else:
                        pygame.mixer.music.set_volume(0.55)

        # ── intro ──────────────────────────────────────────────────────────
        if not intro_done:
            intro_ticks -= 1
            if intro_ticks <= 0:
                intro_done = True

        # ── game logic ────────────────────────────────────────────────────
        if state == "playing" and intro_done:
            gen.update(char.x)
            clouds.update(char.x)
            for seg in gen.segments:
                seg.update()
            char.update(gen.segments, gen.walls, keys, gen.stars)

            # ── enemies ───────────────────────────────────────────────────
            # Convert new spawn points into Enemy objects
            while gen.enemy_spawns:
                ex, ey = gen.enemy_spawns.pop(0)
                enemies.append(Enemy(ex, ey))
            # Update and prune
            for enemy in enemies:
                enemy.update(char.x, char.y, gen.segments)
            enemies = [e for e in enemies if e.x > char.x - gen.PRUNE_BEHIND]
            # Stomp (normal gravity only)
            if not char.gravity_flipped:
                for enemy in enemies:
                    if enemy.stomped_by(char.x, char.y, char.vy):
                        enemy.alive = False
                        char.vy = JUMP_FORCE * 0.6
            # Contact damage
            for enemy in enemies:
                if enemy.hits_player(char.x, char.y) and enemy.can_hit():
                    char.take_damage()
                    enemy.register_hit()

            # ── gravity-flip triggers ──────────────────────────────────────
            pending = []
            for fx in gen.flip_triggers:
                if char.x > fx:
                    char.gravity_flipped = not char.gravity_flipped
                    char.on_ground = False   # let physics re-attach to the new side
                else:
                    pending.append(fx)
            gen.flip_triggers = pending

            # ── sound events ──────────────────────────────────────────────
            # if char.ev_jump:  sounds.play(sounds.snd_jump,  0.7)
            if char.ev_land:  sounds.play(sounds.snd_land,  0.6)
            # if char.ev_step:  sounds.play(sounds.snd_footstep, 0.5)
            if char.ev_star:  sounds.play(sounds.snd_star,  0.9)
            if char.ev_hit:   sounds.play(sounds.snd_hit,   0.8)
            if char.ev_die:   sounds.play(sounds.snd_die,   0.8)
            char.ev_jump = char.ev_land = char.ev_step = char.ev_star = char.ev_hit = char.ev_die = False

            # Camera – smooth follow, slightly ahead in movement direction
            lead     = 50 if char.facing_right else -50
            target_x = char.x - SCREEN_W * 0.38 + lead
            camera_x += (target_x - camera_x) * 0.10
            camera_x  = max(0.0, camera_x)

            # Background colour switches every 2000 px
            pal_idx  = int(char.x / 2000.0) % len(BG_PALETTE)
            bg_color = list(BG_PALETTE[pal_idx])

            # Death
            if not char.alive:
                state = "dead"
                hand_alpha = 0
                for _ in range(28):
                    particles.append({
                        "x":  char.x, "y": char.y - 20,
                        "vx": random.uniform(-6, 6),
                        "vy": random.uniform(-9, -1),
                        "life": 55,
                    })

        # ── particles ─────────────────────────────────────────────────────
        for p in particles:
            p["x"]  += p["vx"]
            p["y"]  += p["vy"]
            p["vy"] += 0.35
            p["life"] -= 1
        particles = [p for p in particles if p["life"] > 0]

        # ── hand animation ────────────────────────────────────────────────
        if state == "dead":
            hand_alpha = min(255, hand_alpha + 8)

        # ── draw ──────────────────────────────────────────────────────────
        screen.fill(tuple(int(c) for c in bg_color))

        clouds.draw(screen, camera_x, tick)
        draw_terrain(screen, gen.segments, gen.walls, int(camera_x))
        draw_flip_triggers(screen, gen.flip_triggers, gen.segments, int(camera_x), tick)
        draw_stars(screen, gen.stars, int(camera_x), tick)
        for enemy in enemies:
            enemy.draw(screen, int(camera_x))
        char.draw(screen, int(camera_x))

        # Particles
        for p in particles:
            alpha_f = p["life"] / 55
            r = max(2, int(5 * alpha_f))
            pygame.draw.circle(screen, WHITE,
                               (int(p["x"] - camera_x), int(p["y"])), r)

        # ── HUD ───────────────────────────────────────────────────────────
        collected = char.stars_collected
        star_txt  = font.render(f"★ {collected}", True, STAR_COLOR)
        dist_txt  = font.render(f"{int(max(0, char.x - 60))} m", True, WHITE)
        screen.blit(star_txt, (20, 20))
        draw_hearts(screen, char.lives)
        screen.blit(dist_txt, (SCREEN_W - dist_txt.get_width() - 20, 20))
        mute_txt = font.render("♪ M" if not music_muted else "✕ M", True,
                               (180, 180, 180) if not music_muted else (220, 80, 80))
        screen.blit(mute_txt, (SCREEN_W - mute_txt.get_width() - 20, 50))

        # Controls hint (fades out)
        if tick < 200:
            alpha = max(0, 255 - int(255 * (tick - 140) / 60)) if tick > 140 else 255
            hint = font.render("left/right Move shift Sprint    space/up Jump    R Restart    M Mute", True,
                               (alpha, alpha, alpha))
            screen.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, SCREEN_H - 38))

        # ── overlays ──────────────────────────────────────────────────────
        if state == "dead":
            # Cartoonist's hand trying to help
            hx = int(SCREEN_W // 2 - 10)
            hy = SCREEN_H // 2 - 80
            draw_hand_pencil(screen, hx, hy, hand_alpha)

            overlay = pygame.Surface((SCREEN_W, 140), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 100))
            screen.blit(overlay, (0, SCREEN_H // 2 - 20))
            msg = big_font.render("GAME OVER!", True, WHITE)
            screen.blit(msg, (SCREEN_W // 2 - msg.get_width() // 2, SCREEN_H // 2 - 10))
            sub = font.render(
                f"{int(max(0, char.x - 60))} m  ★ {char.stars_collected}    Press R to try again",
                True, (220, 220, 220))
            screen.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, SCREEN_H // 2 + 60))

        if not intro_done:
            # Fade-in from black
            fade = pygame.Surface((SCREEN_W, SCREEN_H))
            fade.fill(BLACK)
            fade_alpha = int(255 * intro_ticks / 60)
            fade.set_alpha(fade_alpha)
            screen.blit(fade, (0, 0))
            title = title_font.render("La Linea", True, WHITE)
            screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, SCREEN_H // 2 - 20))

        pygame.display.flip()
        await asyncio.sleep(0)

    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())

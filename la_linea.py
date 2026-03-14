"""
La Linea - A game inspired by the Italian animated TV series by Osvaldo Cavandoli.

Mr. Linea walks along a single white line that forms his entire world.
Jump over gaps and obstacles to reach the end!

Controls:
  Arrow Right / D  - Walk right
  Arrow Left  / A  - Walk left
  Space / Up  / W  - Jump
  R               - Restart
  Escape          - Quit
"""

import pygame
import sys
import math
import random
import array

from constants   import SCREEN_W, SCREEN_H, FPS, GRAVITY, JUMP_FORCE, MOVE_SPEED
from spring_line import SpringLine
from level       import LevelGenerator

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

    @classmethod
    def _footstep(cls):
        """Soft papery tap."""
        n = int(cls.SR * 0.035)
        rng = random.Random(42)
        return cls._pack(
            (rng.uniform(-1, 1) * max(0, 1 - i / n) ** 2 * 0.18
             for i in range(n)))

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

    @classmethod
    def _music(cls):
        """
        La Linea-style accordion loop in C major, 122 BPM.
        Accordion timbre = layered harmonics with fast attack / sustained envelope.
        """
        BPM  = 122
        beat = 60.0 / BPM
        sr   = cls.SR
        s    = cls._sin

        # (note_name, octave, beats)
        FREQS = {
            'C4':261.63,'D4':293.66,'E4':329.63,'F4':349.23,
            'G4':392.00,'A4':440.00,'B4':493.88,
            'C5':523.25,'D5':587.33,'E5':659.25,'G5':783.99,
        }

        melody = [
            # Phrase A – cheerful climb
            ('G4',.5),('A4',.5),('B4',.5),('C5',.5),
            ('B4',.5),('A4',.5),('G4',1.5),
            ('A4',.5),('B4',.5),('C5',.5),('D5',.5),
            ('C5',.5),('B4',.5),('A4',1.5),
            # Phrase B – playful turn
            ('G4',.5),('A4',.5),('B4',.5),('D5',.5),
            ('C5',.5),('B4',.5),('A4',.5),('G4',.5),
            ('E4',.5),('G4',.5),('A4',.5),('G4',.5),('E4',2.0),
            # Phrase C – builds upward
            ('C5',.5),('B4',.5),('A4',.5),('G4',.5),
            ('A4',.5),('B4',.5),('C5',1.5),
            ('D5',.5),('C5',.5),('B4',.5),('A4',.5),
            ('G4',.5),('A4',.5),('B4',1.5),
            # Phrase D – resolution back to start
            ('G4',.5),('E4',.5),('G4',.5),('A4',.5),
            ('B4',.5),('A4',.5),('G4',.5),('E4',.5),
            ('G4',3.0),
        ]

        total_n = int(sr * sum(b for _, b in melody) * beat) + sr
        buf     = [0.0] * total_n
        pos     = 0

        for note, beats in melody:
            freq     = FREQS[note]
            dur      = beats * beat
            note_dur = dur * 0.86            # slight gap between notes
            n        = int(sr * dur)
            n_note   = int(sr * note_dur)
            phase    = 0.0
            ph_inc   = freq / sr

            for i in range(n_note):
                t    = i / sr
                atk  = min(t * 80.0, 1.0)
                rel  = min((note_dur - t) * 55.0, 1.0)
                env  = atk * rel * 0.26
                # Accordion: 5 harmonics
                val  = (s(phase)             * 0.50 +
                        s((phase * 2) % 1.0) * 0.25 +
                        s((phase * 3) % 1.0) * 0.14 +
                        s((phase * 4) % 1.0) * 0.07 +
                        s((phase * 5) % 1.0) * 0.04)
                if pos + i < total_n:
                    buf[pos + i] += val * env
                phase = (phase + ph_inc) % 1.0
            pos += n

        # Soft normalise
        peak = max(abs(v) for v in buf) or 1.0
        if peak > 0.92:
            buf = [v / peak * 0.92 for v in buf]
        return cls._pack(buf[:pos])

    # ── public API ────────────────────────────────────────────────────────

    def __init__(self):
        self.snd_footstep = self._footstep()
        # self.snd_jump     = self._jump()
        self.snd_land     = self._land()
        self.snd_star     = self._star_ding()
        self.snd_die      = self._die()
        self.snd_win      = self._win()
        self.snd_music    = self._music()
        self._music_ch    = pygame.mixer.Channel(0)

    def start_music(self):
        self._music_ch.set_volume(0.55)
        self._music_ch.play(self.snd_music, loops=-1)

    def stop_music(self):
        self._music_ch.stop()

    def play(self, snd, vol=1.0):
        ch = snd.play()
        if ch:
            ch.set_volume(vol)


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


# ─────────────────────────────────────────────────────────────────────────────
# Drawing helpers
# ─────────────────────────────────────────────────────────────────────────────

def draw_terrain(surface, segments, walls, cam_x):
    for seg in segments:
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
        pygame.draw.polygon(surface, STAR_COLOR, pts)
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


def lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * max(0.0, min(1.0, t))) for i in range(3))


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
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
        gen  = LevelGenerator()
        char = MrLinea(60, gen.segments[0].y1)
        return gen, char

    gen, char = new_game()

    camera_x   = 0.0
    state      = "playing"    # playing | dead
    tick       = 0
    bg_color   = list(BG_PALETTE[0])
    particles  = []
    hand_alpha = 0

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
                    gen, char  = new_game()
                    camera_x   = 0.0
                    state      = "playing"
                    particles  = []
                    bg_color   = list(BG_PALETTE[0])
                    hand_alpha = 0
                    tick       = 0
                    sounds.start_music()

        # ── intro ──────────────────────────────────────────────────────────
        if not intro_done:
            intro_ticks -= 1
            if intro_ticks <= 0:
                intro_done = True

        # ── game logic ────────────────────────────────────────────────────
        if state == "playing" and intro_done:
            gen.update(char.x)
            for seg in gen.segments:
                seg.update()
            char.update(gen.segments, gen.walls, keys, gen.stars)

            # ── sound events ──────────────────────────────────────────────
            # if char.ev_jump:  sounds.play(sounds.snd_jump,  0.7)
            if char.ev_land:  sounds.play(sounds.snd_land,  0.6)
            if char.ev_step:  sounds.play(sounds.snd_footstep, 0.5)
            if char.ev_star:  sounds.play(sounds.snd_star,  0.9)
            if char.ev_die:   sounds.play(sounds.snd_die,   0.8)
            char.ev_jump = char.ev_land = char.ev_step = char.ev_star = char.ev_die = False

            # Camera – smooth follow, slightly ahead in movement direction
            lead     = 50 if char.facing_right else -50
            target_x = char.x - SCREEN_W * 0.38 + lead
            camera_x += (target_x - camera_x) * 0.10
            camera_x  = max(0.0, camera_x)

            # Background colour cycles through the palette every 2000 px
            palette_pos = (char.x / 2000.0) % len(BG_PALETTE)
            pal_idx     = int(palette_pos)
            pal_frac    = palette_pos - pal_idx
            pal_next    = (pal_idx + 1) % len(BG_PALETTE)
            target_bg   = lerp_color(BG_PALETTE[pal_idx], BG_PALETTE[pal_next], pal_frac)
            bg_color    = [int(bg_color[i] + (target_bg[i] - bg_color[i]) * 0.04) for i in range(3)]

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

        draw_terrain(screen, gen.segments, gen.walls, int(camera_x))
        draw_stars(screen, gen.stars, int(camera_x), tick)
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
        screen.blit(dist_txt, (SCREEN_W - dist_txt.get_width() - 20, 20))

        # Controls hint (fades out)
        if tick < 200:
            alpha = max(0, 255 - int(255 * (tick - 140) / 60)) if tick > 140 else 255
            hint = font.render("← → Move    Space / ↑ Jump    R Restart", True,
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
            msg = big_font.render("OHH NOOO!", True, WHITE)
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

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()

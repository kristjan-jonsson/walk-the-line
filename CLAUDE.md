# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Walk the Line** is a minimalist browser-playable endless platformer where a single chalk line forms the entire world. The game is built with Python using Pygame and can run as a desktop app or be compiled to WebAssembly for browser play via GitHub Pages.

## Environment Setup

This project uses **uv** (https://docs.astral.sh/uv/) for dependency management, which automatically handles virtual environments. This is the recommended approach.

### Initial Setup

```bash
# uv automatically creates and manages the venv
uv add pygame pygbag
```

### Running Commands

Always prefix Python commands with `uv run` to execute within the virtual environment:

```bash
uv run main.py          # Run the game locally (desktop)
uv run -m pytest        # Run tests (if added)
```

### Important

- **Never activate `.venv` manually** — uv handles this automatically
- Dependencies are defined in `pyproject.toml`
- If issues occur in an old environment, delete `.venv` and run `uv add pygame pygbag` again

## Common Commands

### Desktop Development

```bash
# Run the game locally
uv run main.py

# Build for web (compiles to WebAssembly)
uv run -m pygbag --disable-sound-format-error .

# Serve web build locally
uv run -m http.server -d build/web 8000
# Then open http://localhost:8000
```

### Configuration Files

- `pyproject.toml` — Project metadata and dependencies (pygame-ce>=2.5.0, pygbag>=0.9.0)
- `pygbag.toml` — Excludes unnecessary dirs from web build (.venv, .git, __pycache__, build, dist, etc.)

## Code Architecture

### Entry Point & Game Loop

**main.py** — Contains the core game loop and orchestrates all subsystems:

- **SoundEngine class**: Procedurally generates all audio (no audio files needed). Creates land, star chime, hit, death, and win sounds dynamically using sine wave tables.
- **Event handling**: Input (arrow keys/WASD, space, shift, R for restart, M for mute), quit/pause logic
- **Game state management**: "playing" and "dead" states
- **Camera system**: Smooth following with slight lead in facing direction
- **Background palette cycling**: Color changes every 2000px of progression
- **Particle system**: Explosion effects on death, animated hand pencil on game over

**Key global functions:**
- `draw_terrain()` — Renders spring-line segments and walls (white 3-4px lines)
- `draw_stars()` — Draws pulsing 4-pointed stars collected by player
- `draw_flip_triggers()` — Renders gravity-flip portals (dashed vertical with arrows)
- `draw_hand_pencil()` — Cartoonist's hand appearing on death/game-over

### Character & Game State

**character.py** — Player character:
- Position, velocity, gravity state (normal/flipped)
- Jump mechanics, ground detection
- Star collection tracking and damage system (3 lives)
- Event flags for sound triggers (land, star, hit, die)

**level.py** — LevelGenerator:
- Procedurally generates terrain segments (SpringLine objects)
- Manages walls and obstacles
- Spawns enemies and gravity-flip triggers
- Tracks stars placed on segments
- Prunes off-screen terrain to optimize performance

**spring_line.py** — SpringLine physics:
- Simulates a spring-connected chain of nodes for terrain
- Used for the main chalk line and dynamic deformation under physics
- Methods: `update()`, `y_at(x)`, `contains_x(x)`, `distance_to_line()`

### Visual & Environmental Systems

**clouds.py** — CloudSystem:
- Parallax scrolling cloud layer
- Multiple cloud objects for depth effect

**enemies.py** — Enemy class:
- Basic patrol and pursuit AI
- Collision detection with terrain
- "Stomping" detection (can be destroyed by jumping on them)
- Hit cooldown system to prevent rapid damage

**constants.py** — Game constants:
- Screen dimensions, FPS, physics parameters (gravity, jump force, acceleration)

## Game Design Notes

- **Gravity Flipping**: Gravity-flip triggers allow the player to walk on the underside of the line. Character state tracks `gravity_flipped` boolean, affecting rendering and physics.
- **Stars**: Collected for score. Trigger procedural "chime" sound (C5-E5-G5 chord) and particle effects.
- **Enemies**: Spawned procedurally. Player can stomp them from above (normal gravity) or avoid/take damage. They can't be stomped when gravity is flipped.
- **Procedural Audio**: The SoundEngine uses sine wave lookup tables and frequency envelopes—no external audio files. Background music is loaded from `sound/background-music.ogg`.
- **Camera**: Smoothly follows the player with slight anticipation in facing direction. Maintains field of view for upcoming obstacles.

## Building for the Web

The GitHub Actions workflow (`.github/workflows/pages.yml`) automatically:

1. Installs pygame-ce and pygbag
2. Runs `pygbag --build` to compile Python → WebAssembly (Pyodide-based)
3. Uploads `build/web/` to GitHub Pages

**Local testing before push:**

```bash
uv run -m pygbag --disable-sound-format-error .
uv run -m http.server -d build/web 8000
# Open http://localhost:8000
```

## Assets

- **No audio files** — All sounds are procedurally generated
- **Background music** — `sound/background-music.ogg` (external file required for desktop, handled by Pygame)
- **No image dependencies** — Terrain, stars, and UI drawn with pygame.draw primitives

## Performance Considerations

- Segments are pruned when far behind the player (`PRUNE_BEHIND` constant)
- SoundEngine uses a precomputed sine LUT to avoid repeatedly calling `math.sin()`
- Particles are cleaned up when life <= 0
- Cloud rendering culls off-screen elements

## Debugging Tips

- Disable music mute toggle (M key) to isolate audio issues
- Check `char.alive` and `char.lives` state if collision detection seems off
- Physics debugging: Check `gravity_flipped` state when gravity flipping behavior is unexpected
- Enemy collision: Review `Enemy.hits_player()` and stomp detection logic in `character.py`

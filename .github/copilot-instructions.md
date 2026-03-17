# Walk the Line – Copilot Instructions

Minimalist endless platformer (Python/Pygame). Runs as desktop app or WebAssembly in the browser via GitHub Pages.

## Environment

Uses **uv** for dependency management. Never manually activate `.venv`.

```bash
uv run main.py                                    # Run desktop
uv run -m pygbag --disable-sound-format-error .  # Build for web
uv run -m http.server -d build/web 8000           # Serve web build locally
uv run -m pytest                                  # Run tests (if any)
uv add pygame pygbag                              # Install deps (initial setup)
```

Dependencies: `pyproject.toml` (pygame-ce ≥ 2.5.0, pygbag ≥ 0.9.0)

## Architecture

| File | Role |
|------|------|
| `main.py` | Game loop, SoundEngine (procedural audio via sine LUT), camera, particle system, background palette cycling |
| `character.py` | `Character` class — physics, collision, animation (sprite-based), 3-life damage, gravity-flip state |
| `level.py` | `LevelGenerator` — procedural terrain, walls, enemies, gravity-flip triggers, star placement, segment pruning |
| `spring_line.py` | `SpringLine` — spring-node chain physics for deformable chalk-line terrain |
| `enemies.py` | `Enemy` — patrol/pursuit AI, stomp detection, hit cooldown; `draw_hearts()` HUD |
| `clouds.py` | `CloudSystem` — parallax scrolling background |
| `constants.py` | Shared physics/screen constants (GRAVITY, JUMP_FORCE, SCREEN_W/H, etc.) |

**Key directories:**
- `sprites/` — PNG walk/run/idle/jump frames
- `sound/` — `background-music.ogg` (only external audio; all SFX are procedural)
- `.github/workflows/` — CI/CD: builds WebAssembly and deploys to GitHub Pages

## Conventions

- **Character position** = feet contact point (normal gravity) or head contact point (flipped gravity)
- **Sound events** (`ev_jump`, `ev_land`, `ev_star`, `ev_hit`, `ev_die`) are set in `char.update()` and consumed/cleared in `main.py` each frame — read before clearing
- **Gravity sign**: `grav_sign = 1` (normal) or `-1` (flipped); all vertical physics uses this multiplier
- **Sprite caching**: `_ensure_sprites()` must run after `pygame.display.set_mode()` is called

## Pitfalls

- **Gravity-flipped collision is inverted** — all y-comparisons flip; be careful editing collision logic in `character.py`
- **SpringLine segments get pruned** — accessing segments that have scrolled off-screen will crash; always guard with existence checks
- **Physics constants are coupled** — changing `GRAVITY` requires retuning collision margins (currently 4 px) and follow ranges
- **Web audio** — use `--disable-sound-format-error` flag when building with pygbag to avoid audio codec errors
- **No tests yet** — validate changes by running the game manually; pytest is ready to use if tests are added

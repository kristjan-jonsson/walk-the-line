# Contributing to Walk the Line

Thanks for your interest in contributing to **Walk the Line**! ❤️

This is a small open-source pygame/pygbag game. Contributions of all sizes are welcome — from typo fixes to new levels.

## Quick links

- Source: this repository
- Issues: please use GitHub Issues for bugs / feature requests

## Ways to contribute

- **Bug reports**: include steps to reproduce, expected vs. actual behavior, and your environment (OS, Python version, browser if using web build).
- **Fixes & improvements**: small refactors, performance improvements, readability, typing hints, etc.
- **Content**: new levels, obstacles, sprites, sound effects, music.

## Development setup (desktop)

This project uses Python and `pygame-ce`.

### Using uv (recommended)

```bash
uv add pygame
uv run main.py
```

### Alternative: pip/venv

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Web build (pygbag)

```bash
uv add pygame pygbag
uv run -m pygbag --disable-sound-format-error .
```

Then open the local server output (typically http://localhost:8000).

## Project structure (high level)

- `main.py` — game loop and main entry point
- `level.py` — level generation / level logic
- `levels/` — level data
- `assets/`, `sprites/`, `sound/` — game assets

## Contribution workflow

1. **Fork** the repo
2. Create a feature branch: `git checkout -b my-change`
3. Make your changes
4. Run the game locally and ensure things still work
5. Commit with a descriptive message
6. Open a Pull Request

## Guidelines

- Keep changes focused and easy to review.
- Prefer small PRs over big rewrites.
- If you add assets (images/audio), make sure you have the rights to share them.
- If you add new gameplay features, include a short description in the PR.

## Code style

There isn’t a strict style guide yet. Please keep formatting consistent with the surrounding code.

## License

By contributing, you agree that your contributions will be licensed under the project’s Apache-2.0 license.

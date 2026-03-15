# Walk the Line — La Linea

A browser-playable platformer inspired by Osvaldo Cavandoli's classic Italian animated TV series.
Mr. Linea walks along a single white line that forms his entire world — jump over gaps and obstacles to reach the end!

## Play in the browser

The game is automatically built and deployed to GitHub Pages on every push to `main`:

**➡ https://kristjan-jonsson.github.io/walk-the-line/**

## Controls

| Key | Action |
|---|---|
| `→` / `D` | Walk right |
| `←` / `A` | Walk left |
| `Space` / `↑` / `W` | Jump |
| `R` | Restart |
| `M` | Mute music |
| `Escape` | Quit (desktop only) |

## Run locally (desktop)

### Using uv (recommended)

[uv](https://docs.astral.sh/uv/) manages the virtual environment automatically:

```bash
uv sync
uv run python la_linea.py
```

### Using pip

```bash
pip install pygame-ce
python la_linea.py
```

## Build for the web (pygbag)

### Using uv (recommended)

```bash
uv sync
uv run python -m pygbag --build --width 960 --height 600 la_linea.py
```

Then serve the result with Python's built-in HTTP server:

```bash
# Linux / macOS
python -m http.server 8000 --directory build/web

# Windows (PowerShell)
python -m http.server 8000 --directory build\web
```

Open http://localhost:8000 in your browser to play.

### Using pip

```bash
pip install -r requirements.txt
python -m pygbag --build --width 960 --height 600 la_linea.py
python -m http.server 8000 --directory build/web
```

### Why `pygbag.toml` matters

pygbag scans the entire project directory when packaging. Without an ignore list it
picks up files from the local virtual environment (e.g.
`.venv/Lib/site-packages/pygame/examples/data/boom.wav`) and fails because it cannot
package arbitrary WAV files from dependencies.

The `pygbag.toml` at the repo root tells pygbag to skip `.venv` and other tooling
directories so the build succeeds cleanly.

### Cleaning build artifacts

```bash
# Linux / macOS
rm -rf build/

# Windows (PowerShell)
Remove-Item -Recurse -Force build\
```

## GitHub Actions deployment

The workflow at `.github/workflows/pages.yml` automatically:

1. Checks out the code
2. Installs `pygame-ce` and `pygbag`
3. Runs `pygbag --build` to compile the game to WebAssembly
4. Uploads the `build/web/` directory as the Pages artifact
5. Deploys it to GitHub Pages

To enable Pages in your fork: go to **Settings → Pages** and set the source to **GitHub Actions**.

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
| `Shift` | Sprint |
| `Space` / `↑` / `W` | Jump |
| `R` | Restart |
| `M` | Mute music |
| `Escape` | Quit (desktop only) |

## Run locally (desktop)

### Using uv (recommended)

[uv](https://docs.astral.sh/uv/) manages the virtual environment automatically:

```bash
uv add pygame
uv run python la_linea.py
```

## Build for the web (pygbag)

### Using uv (recommended), use --disable-sound-format-error if error in build

```bash
uv add pygame pygbag
uv run -m pygbag --disable-sound-format-error .
```

Then serve the result with Python's built-in HTTP server:

```bash
uv run -m pygbag --disable-sound-format-error [--width 960 --height 600] .
```

Open http://localhost:8000 in your browser to play.


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

## License

This project is licensed under the Apache License 2.0. See the `LICENSE` file for details.

## Credits

Thanks to RGS_Dev (https://rgsdev.itch.io) for the open character design that is used for main character even though it will be replaced in later stage.

## Disclaimer

This is an open source project provided "AS IS", without warranty of any kind. See the Apache 2.0 license in `LICENSE` for the full terms and conditions.

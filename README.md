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

```bash
pip install pygame-ce
python la_linea.py
```

## Build for the web (pygbag)

```bash
pip install -r requirements.txt
python -m pygbag --build --width 960 --height 600 la_linea.py
# Output is written to build/web/
# Open build/web/index.html in a browser to test locally
```

To serve and test in a browser locally:

```bash
python -m pygbag la_linea.py
# Then open http://localhost:8000
```

## GitHub Actions deployment

The workflow at `.github/workflows/pages.yml` automatically:

1. Checks out the code
2. Installs `pygame-ce` and `pygbag`
3. Runs `pygbag --build` to compile the game to WebAssembly
4. Uploads the `build/web/` directory as the Pages artifact
5. Deploys it to GitHub Pages

To enable Pages in your fork: go to **Settings → Pages** and set the source to **GitHub Actions**.

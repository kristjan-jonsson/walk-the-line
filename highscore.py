"""
highscore.py – Persistent best-distance tracking.

On desktop  → stores highscore.json next to the script.
On web/wasm → uses the browser's localStorage (survives redeployments).
"""

import json
import os
import sys

_IS_WEB = sys.platform == "emscripten"
_LS_KEY = "walk_the_line_highscore"
_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "highscore.json")


def load() -> int:
    """Return the saved highscore (metres), or 0 if none."""
    if _IS_WEB:
        try:
            from js import window
            val = window.localStorage.getItem(_LS_KEY)
            if val is not None:
                return int(val)
        except Exception:
            pass
        return 0
    else:
        try:
            if os.path.exists(_FILE):
                with open(_FILE) as f:
                    return int(json.load(f).get("highscore", 0))
        except Exception:
            pass
        return 0


def save(score: int) -> None:
    """Persist *score* as the new highscore."""
    if _IS_WEB:
        try:
            from js import window
            window.localStorage.setItem(_LS_KEY, str(score))
        except Exception:
            pass
    else:
        try:
            with open(_FILE, "w") as f:
                json.dump({"highscore": score}, f)
        except Exception:
            pass

#!/usr/bin/env python3
"""Development entry point — press Run in PyCharm, or `python run.py`.

Does three things the plain uvicorn command line does not:
  1. puts ./backend on sys.path so the package imports without installation,
  2. loads .env if one exists (nothing else in the project reads it),
  3. turns on reload for both the backend and the frontend.

Production uses the command in render.yaml instead.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))


def load_env(path: Path) -> int:
    """Minimal .env reader. Real environment variables always win.

    Deliberately not python-dotenv: this is fifteen lines and keeps the
    dependency list at two entries.
    """
    if not path.exists():
        return 0
    loaded = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded += 1
    return loaded


if __name__ == "__main__":
    count = load_env(ROOT / ".env")
    if count:
        print(f"run.py: loaded {count} settings from .env")
    else:
        print("run.py: no .env found — using defaults (see .env.example)")

    if os.getenv("ALLOW_NETWORK", "true").strip().lower() in {"0", "false", "no", "off"}:
        print("run.py: WARNING — ALLOW_NETWORK is off. The desk has no bundled")
        print("        corpus, so it will serve an empty edition.")

    import uvicorn

    uvicorn.run(
        "investigatecelra.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
        reload_dirs=[str(ROOT / "backend"), str(ROOT / "frontend")],
    )

"""Locate the project root in both local and container layouts.

Local checkout: <root>/backend/app/...  -> root contains `backend/`.
Container image: /app/app/...           -> /app contains `app/main.py`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache
def project_root() -> Path:
    here = Path(__file__).resolve()
    # A local checkout has <root>/backend/app/main.py; prefer that so we don't
    # stop at the inner `backend` directory, which also has app/main.py.
    for parent in here.parents:
        if (parent / "backend" / "app" / "main.py").exists():
            return parent
    # In the container the project root itself is /app and holds app/main.py.
    for parent in here.parents:
        if (parent / "app" / "main.py").exists():
            return parent
    return here.parents[2]

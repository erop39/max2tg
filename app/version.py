"""Runtime version info for deployment verification."""

from __future__ import annotations

import os
import subprocess


def git_revision(app_root: str | None = None) -> str:
    root = app_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"

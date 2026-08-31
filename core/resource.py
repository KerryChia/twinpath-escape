"""Resource path resolution for both development and PyInstaller builds."""

import sys
from pathlib import Path


def get_base_path() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent


def resource_path(relative: str) -> Path:
    return get_base_path() / relative

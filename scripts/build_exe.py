#!/usr/bin/env python3
"""PyInstaller build script.

Usage:
    python scripts/build_exe.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def main() -> None:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "penguin",
        "--onedir",
        "--windowed",                      # no console window
        "--icon", "assets/penguin.ico",
        "--add-data", "assets;assets",     # bundle sounds + icons
        "--hidden-import", "pyttsx3.drivers",
        "--hidden-import", "pyttsx3.drivers.sapi5",
        "--hidden-import", "pystray._win32",
        "--collect-all", "faster_whisper",
        "--collect-all", "ctranslate2",
        "--collect-all", "silero_vad",
        "penguin/__main__.py",
    ]

    print("Building executable…")
    print(" ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT))
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()

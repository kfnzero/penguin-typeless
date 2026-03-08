"""Discover installed applications and perform fuzzy name matching.

Sources (in priority order):
1. custom_apps from config (user-defined aliases)
2. Windows Registry  HKLM/HKCU Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall
3. Start Menu .lnk shortcuts (%APPDATA% and %ProgramData%)
4. Executable files on PATH
"""

from __future__ import annotations

import logging
import os
import re
import sys
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Minimum fuzzy-match score (0–100) to accept a result
_MIN_SCORE = 65

# Refresh the index every N minutes
_REFRESH_INTERVAL = 30 * 60

# Words to strip when normalising application names
_STRIP_RE = re.compile(
    r"\b(?:for windows|for pc|portable|setup|installer|uninstall|update|"
    r"x64|x86|64-bit|32-bit|\d+\.\d+[\.\d]*)\b",
    re.IGNORECASE,
)


def _normalise(name: str) -> str:
    name = _STRIP_RE.sub("", name)
    return re.sub(r"\s{2,}", " ", name).strip()


class ProgramIndex:
    """
    Maintains a mapping of {normalised_name: exe_path} and provides
    fuzzy search.

    Usage::

        idx = ProgramIndex(custom_apps={"瀏覽器": "chrome.exe"})
        idx.build()
        path = idx.find("chrome")   # → "C:\\...\\chrome.exe" or None
    """

    def __init__(self, custom_apps: dict[str, str] | None = None) -> None:
        self._custom: dict[str, str] = {
            k.lower(): v for k, v in (custom_apps or {}).items()
        }
        self._index: dict[str, str] = {}   # lower name → exe path
        self._lock = threading.RLock()
        self._last_build: float = 0.0
        self._build_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self, blocking: bool = True) -> None:
        """Scan all sources and rebuild the index."""
        if blocking:
            self._do_build()
        else:
            t = threading.Thread(target=self._do_build, daemon=True)
            t.start()
            self._build_thread = t

    def find(self, query: str) -> str | None:
        """Return the best-matching executable path, or None.

        Also triggers a background refresh if the index is stale.
        """
        if time.monotonic() - self._last_build > _REFRESH_INTERVAL:
            self.build(blocking=False)

        query_norm = _normalise(query).lower()

        with self._lock:
            # 1. Exact custom alias
            if query_norm in self._custom:
                return self._custom[query_norm]

            # 2. Exact index match
            if query_norm in self._index:
                return self._index[query_norm]

            # 3. Fuzzy match
            return self._fuzzy_find(query_norm)

    # ------------------------------------------------------------------
    # Build helpers
    # ------------------------------------------------------------------

    def _do_build(self) -> None:
        logger.info("ProgramIndex: rebuilding...")
        new_index: dict[str, str] = {}

        if sys.platform == "win32":
            new_index.update(self._scan_registry())
            new_index.update(self._scan_startmenu())

        new_index.update(self._scan_path())

        with self._lock:
            self._index = new_index
        self._last_build = time.monotonic()
        logger.info("ProgramIndex: %d entries", len(new_index))

    # -- Registry -------------------------------------------------------

    def _scan_registry(self) -> dict[str, str]:
        result: dict[str, str] = {}
        try:
            import winreg
            keys = [
                (winreg.HKEY_LOCAL_MACHINE,
                 r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE,
                 r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER,
                 r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            ]
            for hive, path in keys:
                try:
                    with winreg.OpenKey(hive, path) as key:
                        for i in range(winreg.QueryInfoKey(key)[0]):
                            try:
                                sub_name = winreg.EnumKey(key, i)
                                with winreg.OpenKey(key, sub_name) as sub:
                                    name = _reg_str(sub, "DisplayName")
                                    exe = _reg_str(sub, "DisplayIcon") or \
                                          _reg_str(sub, "InstallLocation")
                                    if name and exe:
                                        exe = exe.split(",")[0].strip('"')
                                        if exe.lower().endswith(".exe") and Path(exe).exists():
                                            result[_normalise(name).lower()] = exe
                            except OSError:
                                continue
                except OSError:
                    continue
        except ImportError:
            pass
        return result

    # -- Start Menu shortcuts -------------------------------------------

    def _scan_startmenu(self) -> dict[str, str]:
        result: dict[str, str] = {}
        dirs = [
            Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu",
            Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft" / "Windows" / "Start Menu",
        ]
        for d in dirs:
            if not d.exists():
                continue
            for lnk in d.rglob("*.lnk"):
                try:
                    exe = _resolve_lnk(lnk)
                    if exe and exe.lower().endswith(".exe") and Path(exe).exists():
                        name = lnk.stem
                        result[_normalise(name).lower()] = exe
                except Exception:
                    continue
        return result

    # -- PATH executables -----------------------------------------------

    def _scan_path(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for d in os.environ.get("PATH", "").split(os.pathsep):
            p = Path(d)
            if not p.is_dir():
                continue
            for exe in p.glob("*.exe"):
                name = exe.stem
                result[_normalise(name).lower()] = str(exe)
        return result

    # -- Fuzzy matching -------------------------------------------------

    def _fuzzy_find(self, query: str) -> str | None:
        try:
            from rapidfuzz import process, fuzz
            # Combine custom aliases and index for searching
            candidates = dict(self._custom)
            candidates.update(self._index)
            if not candidates:
                return None
            match = process.extractOne(
                query,
                candidates.keys(),
                scorer=fuzz.WRatio,
                score_cutoff=_MIN_SCORE,
            )
            if match:
                key, score, _ = match
                logger.debug("Fuzzy match: %r → %r (score=%d)", query, key, score)
                return candidates[key]
        except ImportError:
            pass
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reg_str(key, value_name: str) -> str:
    try:
        import winreg
        val, _ = winreg.QueryValueEx(key, value_name)
        return str(val)
    except OSError:
        return ""


def _resolve_lnk(path: Path) -> str | None:
    """Resolve a Windows .lnk shortcut to its target path."""
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(path))
        return shortcut.Targetpath or None
    except Exception:
        pass
    # Fallback: try pythoncom-free byte parsing (basic)
    try:
        data = path.read_bytes()
        # .lnk files have target path starting at offset 0x4C in older format
        # This is unreliable; prefer win32com
        if len(data) > 0x4C and data[:4] == b"L\x00\x00\x00":
            return None  # Skip without win32com
    except Exception:
        pass
    return None

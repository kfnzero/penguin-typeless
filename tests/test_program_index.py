"""Unit tests for ProgramIndex (no Windows registry needed)."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from penguin.programs.index import ProgramIndex, _normalise


# ---------------------------------------------------------------------------
# Name normalisation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("Google Chrome", "Google Chrome"),
    ("Spotify x64", "Spotify"),
    ("Node.js 20.11.0", "Node.js"),
    ("  Notepad++ ", "Notepad++"),
    ("VLC media player 3.0.20", "VLC media player"),
])
def test_normalise(raw, expected):
    assert _normalise(raw) == expected


# ---------------------------------------------------------------------------
# Custom app aliasing
# ---------------------------------------------------------------------------

def test_custom_app_exact():
    idx = ProgramIndex(custom_apps={"瀏覽器": "chrome.exe"})
    assert idx.find("瀏覽器") == "chrome.exe"


def test_custom_app_case_insensitive():
    idx = ProgramIndex(custom_apps={"Chrome": "chrome.exe"})
    assert idx.find("chrome") == "chrome.exe"


# ---------------------------------------------------------------------------
# Index search
# ---------------------------------------------------------------------------

def _make_index(entries: dict) -> ProgramIndex:
    idx = ProgramIndex()
    idx._index = {k.lower(): v for k, v in entries.items()}
    idx._last_build = float("inf")   # prevent auto-rebuild
    return idx


def test_exact_match():
    idx = _make_index({"notepad": "notepad.exe"})
    assert idx.find("notepad") == "notepad.exe"


def test_no_match():
    idx = _make_index({"notepad": "notepad.exe"})
    result = idx.find("xyzsoftware_nonexistent")
    assert result is None


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="rapidfuzz available but test is platform-agnostic",
)
def test_fuzzy_match():
    idx = _make_index({"google chrome": "chrome.exe", "spotify": "spotify.exe"})
    result = idx.find("chrome")
    assert result == "chrome.exe"

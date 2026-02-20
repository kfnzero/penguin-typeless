"""Unit tests for intent parsing (no external dependencies required)."""

import pytest

from penguin.commands.intent import ParsedIntent, parse_intent


# ---------------------------------------------------------------------------
# Chinese open-app patterns
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected_target", [
    ("幫我開啟 Chrome", "Chrome"),
    ("打開記事本", "記事本"),
    ("請開啟 Spotify", "Spotify"),
    ("開一下小畫家", "小畫家"),
    ("我要開 Discord", "Discord"),
    ("我想用 Word", "Word"),
    ("啟動 Steam", "Steam"),
])
def test_parse_open_zh(text, expected_target):
    result = parse_intent(text)
    assert result.action == "open"
    assert result.target.lower() == expected_target.lower()


# ---------------------------------------------------------------------------
# English open-app patterns
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected_target", [
    ("open Chrome", "Chrome"),
    ("launch Spotify", "Spotify"),
    ("start notepad", "notepad"),
    ("run Steam", "Steam"),
    ("please open Discord", "Discord"),
    ("can you open Word", "Word"),
    ("open Chrome for me", "Chrome"),
])
def test_parse_open_en(text, expected_target):
    result = parse_intent(text)
    assert result.action == "open"
    assert result.target.lower() == expected_target.lower()


# ---------------------------------------------------------------------------
# Unknown / unrecognised
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "你好",
    "hello",
    "",
    "什麼時候",
    "what time is it",
])
def test_parse_unknown(text):
    result = parse_intent(text)
    assert result.action == "unknown"
    assert result.target == ""


# ---------------------------------------------------------------------------
# Noise word stripping
# ---------------------------------------------------------------------------

def test_strip_noise_words():
    result = parse_intent("幫我開啟 Chrome 程式")
    assert result.action == "open"
    assert "程式" not in result.target


def test_raw_preserved():
    text = "open Notepad for me"
    result = parse_intent(text)
    assert result.raw == text

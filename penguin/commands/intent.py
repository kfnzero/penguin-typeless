"""Parse transcribed text into structured commands.

Supports Chinese and English open-app commands.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Open-app patterns
# ---------------------------------------------------------------------------

_OPEN_ZH = [
    # 幫我開啟 XXX / 請打開 XXX / 開一下 XXX
    r"(?:幫我|請|麻煩)?(?:開啟|打開|啟動|執行|開|run)\s*(?:一下\s*)?(.+?)(?:程式|應用|app)?$",
    r"(?:我要|我想)\s*(?:開|用|啟動)\s*(.+)",
]

_OPEN_EN = [
    r"(?:please\s+)?(?:open|launch|start|run|execute)\s+(.+?)(?:\s+(?:for me|please))?$",
    r"(?:can you\s+)?(?:open|launch|start)\s+(.+)",
]

_ALL_PATTERNS = [
    (re.compile(p, re.IGNORECASE | re.UNICODE), "open")
    for p in _OPEN_ZH + _OPEN_EN
]

# Words to strip from extracted app name
_NOISE_WORDS = re.compile(
    r"\b(?:程式|應用程式|軟體|app|application|please|for me|幫我|一下)\b",
    re.IGNORECASE | re.UNICODE,
)


@dataclass
class ParsedIntent:
    action: str    # "open" | "unknown"
    target: str    # application name, empty string if action == "unknown"
    raw: str


def parse_intent(text: str) -> ParsedIntent:
    """Extract the intent and target from a transcribed command.

    Examples::

        parse_intent("幫我開啟 Chrome") → ParsedIntent(action="open", target="Chrome", ...)
        parse_intent("open Spotify")    → ParsedIntent(action="open", target="Spotify", ...)
        parse_intent("hello")           → ParsedIntent(action="unknown", target="", ...)
    """
    text = text.strip()
    for pattern, action in _ALL_PATTERNS:
        m = pattern.search(text)
        if m:
            target = m.group(1).strip()
            target = _NOISE_WORDS.sub("", target).strip()
            target = re.sub(r"\s{2,}", " ", target)
            if target:
                return ParsedIntent(action=action, target=target, raw=text)

    return ParsedIntent(action="unknown", target="", raw=text)

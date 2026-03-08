"""System tray icon using pystray."""

from __future__ import annotations

import logging
import threading
from enum import Enum, auto
from typing import Callable

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


class TrayState(Enum):
    IDLE = auto()
    LISTENING = auto()
    PROCESSING = auto()


# Colour palette per state
_STATE_COLORS = {
    TrayState.IDLE:       ("#4A90D9", "#FFFFFF"),   # blue bg, white icon
    TrayState.LISTENING:  ("#27AE60", "#FFFFFF"),   # green bg — "listening"
    TrayState.PROCESSING: ("#F39C12", "#FFFFFF"),   # amber bg — "thinking"
}

_ICON_SIZE = 64


def _make_icon(state: TrayState) -> Image.Image:
    """Generate a simple coloured circle icon for the given state."""
    bg, fg = _STATE_COLORS[state]
    img = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Filled circle background
    draw.ellipse([2, 2, _ICON_SIZE - 2, _ICON_SIZE - 2], fill=bg)
    # Microphone body (rect + arc)
    cx, cy = _ICON_SIZE // 2, _ICON_SIZE // 2
    draw.rectangle([cx - 8, cy - 18, cx + 8, cy + 4], fill=fg, width=0)
    draw.ellipse([cx - 8, cy - 4, cx + 8, cy + 14], fill=fg)
    # Stand
    draw.arc([cx - 14, cy + 4, cx + 14, cy + 22], start=0, end=180, fill=fg, width=3)
    draw.line([cx, cy + 22, cx, cy + 28], fill=fg, width=3)
    draw.line([cx - 6, cy + 28, cx + 6, cy + 28], fill=fg, width=3)
    return img


class TrayController:
    """
    Manages the system tray icon and menu.

    Args:
        on_settings: Called when the user clicks "設定".
        on_quit: Called when the user clicks "結束".
    """

    def __init__(
        self,
        on_settings: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None,
    ) -> None:
        self._on_settings = on_settings
        self._on_quit = on_quit
        self._icon = None
        self._state = TrayState.IDLE
        self._icons: dict[TrayState, Image.Image] = {
            s: _make_icon(s) for s in TrayState
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Run the tray icon in a daemon thread."""
        t = threading.Thread(target=self._run, daemon=True, name="TrayThread")
        t.start()

    def set_state(self, state: TrayState) -> None:
        self._state = state
        if self._icon:
            self._icon.icon = self._icons[state]

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        try:
            import pystray

            menu = pystray.Menu(
                pystray.MenuItem("Penguin 語音助理", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("設定", self._click_settings),
                pystray.MenuItem("結束", self._click_quit),
            )
            self._icon = pystray.Icon(
                "penguin",
                icon=self._icons[TrayState.IDLE],
                title="Penguin 語音助理",
                menu=menu,
            )
            self._icon.run()
        except Exception as exc:
            logger.error("Tray icon failed: %s", exc)

    def _click_settings(self, icon, item) -> None:
        if self._on_settings:
            threading.Thread(target=self._on_settings, daemon=True).start()

    def _click_quit(self, icon, item) -> None:
        icon.stop()
        if self._on_quit:
            self._on_quit()

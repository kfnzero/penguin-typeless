"""Non-blocking audio feedback player."""

from __future__ import annotations

import logging
import threading
import wave
from pathlib import Path

logger = logging.getLogger(__name__)

_ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "sounds"


def play_sound(name: str) -> None:
    """Play a .wav file from assets/sounds/ in a daemon thread (non-blocking).

    Args:
        name: Filename without extension, e.g. ``"wake_ack"`` or ``"command_done"``.
    """
    path = _ASSETS_DIR / f"{name}.wav"
    if not path.exists():
        logger.debug("Sound file not found: %s", path)
        return
    t = threading.Thread(target=_play, args=(path,), daemon=True)
    t.start()


def _play(path: Path) -> None:
    try:
        import pyaudio
        with wave.open(str(path), "rb") as wf:
            pa = pyaudio.PyAudio()
            stream = pa.open(
                format=pa.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
            )
            data = wf.readframes(1024)
            while data:
                stream.write(data)
                data = wf.readframes(1024)
            stream.stop_stream()
            stream.close()
            pa.terminate()
    except Exception as exc:
        logger.debug("play_sound failed for %s: %s", path.name, exc)

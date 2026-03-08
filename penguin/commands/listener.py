"""Record audio for a fixed duration after wake word detection."""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable

from penguin.utils.events import AudioChunk, TranscriptEvent

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 16000
_SAMPLE_WIDTH = 2  # int16 bytes per sample


class CommandListener:
    """
    Collects raw audio for ``capture_seconds`` then calls ``on_done``
    with the concatenated PCM bytes.

    This component sits between the main audio stream and the Transcriber.
    When armed (via ``arm()``), it collects the next N seconds of audio
    regardless of VAD — we want to capture even pauses in speech.
    """

    def __init__(
        self,
        capture_seconds: float = 5.0,
        on_done: Callable[[bytes], None] | None = None,
    ) -> None:
        self._capture_seconds = capture_seconds
        self._on_done = on_done
        self._armed = threading.Event()
        self._chunks: list[bytes] = []
        self._lock = threading.Lock()
        self._arm_time: float = 0.0

    @property
    def is_armed(self) -> bool:
        return self._armed.is_set()

    def arm(self) -> None:
        """Start collecting audio. Call this after wake word is detected."""
        with self._lock:
            self._chunks.clear()
            self._arm_time = time.monotonic()
        self._armed.set()
        logger.debug("CommandListener armed (%.1f s window)", self._capture_seconds)

    def feed(self, chunk: AudioChunk) -> None:
        """Feed raw audio chunks (called from the audio capture thread)."""
        if not self._armed.is_set():
            return

        with self._lock:
            self._chunks.append(chunk.data)
            elapsed = time.monotonic() - self._arm_time

        if elapsed >= self._capture_seconds:
            self._armed.clear()
            with self._lock:
                pcm = b"".join(self._chunks)
                self._chunks.clear()
            logger.debug("CommandListener captured %.2f s of audio (%d bytes)",
                         elapsed, len(pcm))
            if self._on_done:
                threading.Thread(target=self._on_done, args=(pcm,), daemon=True).start()

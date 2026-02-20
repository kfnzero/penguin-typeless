"""Wake word detection using faster-whisper tiny + fuzzy keyword matching.

Strategy
--------
1. VAD passes speech chunks into a rolling buffer.
2. Every ``wake_window_seconds`` of audio, run faster-whisper tiny.
3. Check if the transcript contains the configured wake word (fuzzy match).
4. Fire a WakeEvent and enforce a debounce cooldown.
"""

from __future__ import annotations

import logging
import struct
import time
from collections import deque
from threading import Event, Thread
from typing import Callable

from penguin.utils.events import SpeechChunk, WakeEvent

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 16000
_SAMPLE_WIDTH = 2  # int16


class WakeWordEngine:
    """
    Consumes SpeechChunks and fires a WakeEvent when the wake word is heard.

    Args:
        model_dir: Directory where Whisper models are cached.
        model_size: Whisper model name (e.g. "tiny").
        language: Whisper language hint ("zh", "en", "auto").
        wake_word: The trigger phrase (e.g. "小助手").
        threshold: Fuzzy-match threshold 0–1.
        window_seconds: Rolling audio window sent to Whisper.
        debounce_seconds: Minimum time between two wake events.
        device: "cpu" or "cuda".
        compute_type: CTranslate2 compute type (e.g. "int8").
        on_wake: Callback called with WakeEvent in a daemon thread.
    """

    def __init__(
        self,
        model_dir: str,
        model_size: str = "tiny",
        language: str = "zh",
        wake_word: str = "小助手",
        threshold: float = 0.7,
        window_seconds: float = 2.0,
        debounce_seconds: float = 2.0,
        device: str = "cpu",
        compute_type: str = "int8",
        on_wake: Callable[[WakeEvent], None] | None = None,
    ) -> None:
        self._model_dir = model_dir
        self._model_size = model_size
        self._language = language if language != "auto" else None
        self._wake_word = wake_word.strip()
        self._threshold = threshold
        self._window_bytes = int(window_seconds * _SAMPLE_RATE * _SAMPLE_WIDTH)
        self._debounce = debounce_seconds
        self._device = device
        self._compute_type = compute_type
        self._on_wake = on_wake

        self._model = None
        self._buffer: deque[bytes] = deque()
        self._buffer_size = 0
        self._last_wake_time: float = 0.0
        self._stop_event = Event()
        self._worker: Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._stop_event.clear()
        self._load_model()
        logger.info(
            "WakeWordEngine started (wake_word=%r, model=%s, threshold=%.2f)",
            self._wake_word, self._model_size, self._threshold
        )

    def stop(self) -> None:
        self._stop_event.set()

    def feed(self, chunk: SpeechChunk) -> None:
        """Feed a VAD-confirmed speech chunk into the rolling buffer."""
        self._buffer.append(chunk.data)
        self._buffer_size += len(chunk.data)

        # Trim buffer to window size
        while self._buffer_size > self._window_bytes and self._buffer:
            removed = self._buffer.popleft()
            self._buffer_size -= len(removed)

        # Once we have a full window, check for wake word
        if self._buffer_size >= self._window_bytes:
            self._check()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
                download_root=self._model_dir,
            )
            logger.info("Wake word model loaded: faster-whisper %s", self._model_size)
        except Exception as exc:
            logger.error("Failed to load wake word model: %s", exc)

    def _check(self) -> None:
        if self._model is None:
            return

        now = time.monotonic()
        if now - self._last_wake_time < self._debounce:
            return

        pcm = b"".join(self._buffer)
        transcript = self._transcribe(pcm)
        if not transcript:
            return

        logger.debug("Wake window transcript: %r", transcript)
        score = self._match_score(transcript)

        if score >= self._threshold:
            self._last_wake_time = now
            event = WakeEvent(transcript=transcript, confidence=score)
            logger.info("WAKE WORD detected! %r (score=%.2f)", self._wake_word, score)
            self._buffer.clear()
            self._buffer_size = 0
            if self._on_wake:
                Thread(target=self._on_wake, args=(event,), daemon=True).start()

    def _transcribe(self, pcm: bytes) -> str:
        """Convert PCM int16 bytes → float32 numpy array → Whisper."""
        try:
            import numpy as np
            samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
            kwargs: dict = dict(
                beam_size=1,
                best_of=1,
                temperature=0.0,
                without_timestamps=True,
                condition_on_previous_text=False,
            )
            if self._language:
                kwargs["language"] = self._language

            segments, _ = self._model.transcribe(samples, **kwargs)
            return " ".join(s.text for s in segments).strip()
        except Exception as exc:
            logger.debug("Wake transcription error: %s", exc)
            return ""

    def _match_score(self, transcript: str) -> float:
        """Return fuzzy match score (0–1) between wake word and transcript."""
        try:
            from rapidfuzz import fuzz
            t = transcript.lower()
            w = self._wake_word.lower()
            if w in t:
                return 1.0
            return fuzz.partial_ratio(w, t) / 100.0
        except ImportError:
            # Fallback: exact substring
            return 1.0 if self._wake_word.lower() in transcript.lower() else 0.0

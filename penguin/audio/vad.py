"""Voice Activity Detection using silero-vad.

Wraps silero-vad and exposes a simple ``is_speech(pcm_bytes) -> bool`` API.
The model is loaded lazily on first use so import time stays low.
"""

from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# silero-vad expects 512 samples @ 16kHz (32ms) or 256 @ 8kHz
# Our capture produces 1280 samples (80ms) — we split into 512-sample windows
_WINDOW_SAMPLES = 512
_WINDOW_BYTES = _WINDOW_SAMPLES * 2  # int16 → 2 bytes per sample


class VAD:
    """
    Thin wrapper around silero-vad.

    Example::

        vad = VAD(threshold=0.5)
        if vad.is_speech(chunk.data):
            ...
    """

    def __init__(self, threshold: float = 0.5, sample_rate: int = 16000) -> None:
        self._threshold = threshold
        self._sample_rate = sample_rate
        self._model = None
        self._utils = None

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False,
            )
            self._model = model
            self._utils = utils
            logger.info("silero-vad loaded (threshold=%.2f)", self._threshold)
        except Exception as exc:
            logger.warning("silero-vad load failed (%s); VAD disabled (all chunks pass)", exc)

    def is_speech(self, pcm_bytes: bytes) -> bool:
        """Return True if *pcm_bytes* (int16 LE) likely contains speech."""
        self._load()
        if self._model is None:
            return True  # VAD unavailable → pass everything through

        try:
            import torch
            # Process in 512-sample windows; return True if any window is speech
            for offset in range(0, len(pcm_bytes) - _WINDOW_BYTES + 1, _WINDOW_BYTES):
                window = pcm_bytes[offset : offset + _WINDOW_BYTES]
                samples = struct.unpack(f"{_WINDOW_SAMPLES}h", window)
                tensor = torch.tensor(samples, dtype=torch.float32) / 32768.0
                prob = self._model(tensor, self._sample_rate).item()
                if prob >= self._threshold:
                    return True
        except Exception as exc:
            logger.debug("VAD inference error: %s", exc)
            return True  # on error, pass through

        return False

    def reset(self) -> None:
        """Reset silero internal state (call between utterances)."""
        if self._model is not None:
            try:
                self._model.reset_states()
            except Exception:
                pass

"""High-accuracy command transcription using faster-whisper small."""

from __future__ import annotations

import logging

import numpy as np

from penguin.utils.events import TranscriptEvent

logger = logging.getLogger(__name__)


class Transcriber:
    """
    Wraps faster-whisper for command transcription.

    The model is pre-loaded at startup to avoid latency on first use.

    Args:
        model_dir: Local directory for model cache.
        model_size: Whisper model (e.g. "small").
        language: Language hint ("zh", "en", None = auto-detect).
        device: "cpu" or "cuda".
        compute_type: CTranslate2 precision.
    """

    def __init__(
        self,
        model_dir: str,
        model_size: str = "small",
        language: str | None = "zh",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self._model_dir = model_dir
        self._model_size = model_size
        self._language = language if language != "auto" else None
        self._device = device
        self._compute_type = compute_type
        self._model = None

    def load(self) -> None:
        """Pre-load the model (call at application startup)."""
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
            logger.info("Transcriber model loaded: faster-whisper %s", self._model_size)
        except Exception as exc:
            logger.error("Failed to load transcriber model: %s", exc)

    def transcribe(self, pcm_bytes: bytes, sample_rate: int = 16000) -> TranscriptEvent:
        """Transcribe PCM int16 audio bytes to text.

        Returns:
            TranscriptEvent with the recognised text (empty string on failure).
        """
        if self._model is None:
            self.load()
        if self._model is None:
            return TranscriptEvent(text="", language=self._language or "unknown")

        try:
            samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            kwargs: dict = dict(
                beam_size=5,
                best_of=5,
                temperature=0.0,
                without_timestamps=True,
                condition_on_previous_text=False,
                vad_filter=True,          # built-in VAD to trim silence
            )
            if self._language:
                kwargs["language"] = self._language

            segments, info = self._model.transcribe(samples, **kwargs)
            text = " ".join(s.text for s in segments).strip()
            lang = info.language
            logger.info("Transcribed [%s]: %r", lang, text)
            return TranscriptEvent(text=text, language=lang)
        except Exception as exc:
            logger.error("Transcription failed: %s", exc)
            return TranscriptEvent(text="", language=self._language or "unknown")

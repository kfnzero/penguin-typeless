"""Continuous microphone capture producing fixed-size PCM chunks."""

from __future__ import annotations

import logging
import queue
import threading
from typing import Callable

import pyaudio

from penguin.utils.events import AudioChunk

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000      # Hz — Whisper expects 16 kHz
CHANNELS = 1             # mono
SAMPLE_WIDTH = 2         # bytes, int16
CHUNK_MS = 80            # milliseconds per chunk — good balance for VAD
CHUNK_FRAMES = SAMPLE_RATE * CHUNK_MS // 1000   # 1280 frames


class AudioCapture:
    """
    Streams audio from the default microphone.

    Usage::

        capture = AudioCapture()
        capture.start(callback=my_fn)   # callback receives AudioChunk
        ...
        capture.stop()

    Or use as a context manager::

        with AudioCapture() as capture:
            for chunk in capture.iter_chunks():
                ...
    """

    def __init__(self, device_index: int | None = None) -> None:
        self._device_index = device_index
        self._pa: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None
        self._callback: Callable[[AudioChunk], None] | None = None
        self._running = threading.Event()
        self._q: queue.Queue[AudioChunk] = queue.Queue(maxsize=100)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, callback: Callable[[AudioChunk], None] | None = None) -> None:
        """Open the audio stream. If *callback* is provided it is called for
        each chunk in the capture thread; otherwise chunks are queued."""
        if self._running.is_set():
            return
        self._callback = callback
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            input_device_index=self._device_index,
            frames_per_buffer=CHUNK_FRAMES,
            stream_callback=self._pyaudio_callback,
        )
        self._running.set()
        self._stream.start_stream()
        logger.info("AudioCapture started (device=%s, rate=%d Hz, chunk=%d ms)",
                    self._device_index, SAMPLE_RATE, CHUNK_MS)

    def stop(self) -> None:
        self._running.clear()
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._pa:
            self._pa.terminate()
            self._pa = None
        logger.info("AudioCapture stopped")

    def iter_chunks(self) -> "Generator[AudioChunk, None, None]":
        """Block-iterate over captured chunks (only valid after start())."""
        while self._running.is_set():
            try:
                yield self._q.get(timeout=0.2)
            except queue.Empty:
                continue

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "AudioCapture":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _pyaudio_callback(
        self,
        in_data: bytes,
        frame_count: int,
        time_info: dict,
        status_flags: int,
    ) -> tuple[None, int]:
        chunk = AudioChunk(data=in_data, sample_rate=SAMPLE_RATE)
        if self._callback:
            self._callback(chunk)
        else:
            try:
                self._q.put_nowait(chunk)
            except queue.Full:
                pass  # drop oldest chunk rather than blocking
        return (None, pyaudio.paContinue)

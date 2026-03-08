"""Match a parsed intent to a program and launch it."""

from __future__ import annotations

import logging
import subprocess
import threading

import pyttsx3

from penguin.commands.intent import ParsedIntent
from penguin.programs.index import ProgramIndex

logger = logging.getLogger(__name__)


class CommandDispatcher:
    """
    Receives ParsedIntent, looks up the program, launches it, and
    speaks a response via TTS.

    Args:
        program_index: Pre-built ProgramIndex.
        tts_rate: TTS speaking rate (words per minute).
        tts_voice_index: SAPI5 voice index (0 = first installed voice).
    """

    def __init__(
        self,
        program_index: ProgramIndex,
        tts_rate: int = 180,
        tts_voice_index: int = 0,
    ) -> None:
        self._index = program_index
        self._tts_rate = tts_rate
        self._tts_voice_index = tts_voice_index
        self._engine: pyttsx3.Engine | None = None
        self._tts_lock = threading.Lock()

    def dispatch(self, intent: ParsedIntent) -> None:
        """Handle a parsed intent. Safe to call from any thread."""
        if intent.action == "open":
            self._handle_open(intent.target, intent.raw)
        else:
            self._speak("抱歉，我不太明白，可以再說一次嗎？")

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _handle_open(self, target: str, raw: str) -> None:
        exe = self._index.find(target)
        if exe:
            logger.info("Launching: %s → %s", target, exe)
            self._speak(f"好的，開啟 {target}")
            try:
                subprocess.Popen([exe], shell=False)  # noqa: S603
            except Exception as exc:
                logger.error("Failed to launch %s: %s", exe, exc)
                self._speak(f"啟動 {target} 時發生錯誤")
        else:
            logger.warning("Program not found: %r", target)
            self._speak(f"找不到 {target}，請確認程式名稱")

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------

    def _speak(self, text: str) -> None:
        """Run TTS in a daemon thread (non-blocking)."""
        t = threading.Thread(target=self._tts_run, args=(text,), daemon=True)
        t.start()

    def _tts_run(self, text: str) -> None:
        with self._tts_lock:
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", self._tts_rate)
                voices = engine.getProperty("voices")
                if voices and self._tts_voice_index < len(voices):
                    engine.setProperty("voice", voices[self._tts_voice_index].id)
                engine.say(text)
                engine.runAndWait()
                engine.stop()
            except Exception as exc:
                logger.error("TTS error: %s", exc)

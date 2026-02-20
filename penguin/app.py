"""MainApplication — wires all components together and manages their lifecycles."""

from __future__ import annotations

import logging
import threading

from penguin.audio.capture import AudioCapture
from penguin.audio.player import play_sound
from penguin.audio.vad import VAD
from penguin.commands.dispatcher import CommandDispatcher
from penguin.commands.intent import parse_intent
from penguin.commands.listener import CommandListener
from penguin.programs.index import ProgramIndex
from penguin.settings.manager import SettingsManager
from penguin.settings.schema import AssistantConfig
from penguin.stt.transcriber import Transcriber
from penguin.tray.controller import TrayController, TrayState
from penguin.utils.events import AudioChunk, SpeechChunk, WakeEvent
from penguin.utils.logging_config import setup_logging
from penguin.wake.engine import WakeWordEngine

logger = logging.getLogger(__name__)


class MainApplication:
    """
    Top-level coordinator.

    Lifecycle::

        app = MainApplication()
        app.run()        # blocks until quit
    """

    def __init__(self) -> None:
        self._sm = SettingsManager()
        self._cfg: AssistantConfig = self._sm.load()

        setup_logging(log_dir=self._sm.config_dir)
        logger.info("Penguin Voice Assistant starting…")

        model_dir = str(self._sm.model_dir)

        # --- Audio ---
        self._capture = AudioCapture()
        self._vad = VAD(threshold=self._cfg.vad_threshold)

        # --- Wake word ---
        self._wake_engine = WakeWordEngine(
            model_dir=model_dir,
            model_size=self._cfg.wake_model,
            language=self._cfg.language,
            wake_word=self._cfg.name,
            threshold=self._cfg.wake_threshold,
            window_seconds=self._cfg.wake_window_seconds,
            device=self._cfg.device,
            compute_type=self._cfg.compute_type,
            on_wake=self._on_wake,
        )

        # --- Command pipeline ---
        self._listener = CommandListener(
            capture_seconds=self._cfg.command_capture_seconds,
            on_done=self._on_command_audio,
        )
        self._transcriber = Transcriber(
            model_dir=model_dir,
            model_size=self._cfg.command_model,
            language=self._cfg.language if self._cfg.language != "auto" else None,
            device=self._cfg.device,
            compute_type=self._cfg.compute_type,
        )

        # --- Programs + Dispatcher ---
        self._program_index = ProgramIndex(custom_apps=self._cfg.custom_apps)
        self._dispatcher = CommandDispatcher(
            program_index=self._program_index,
            tts_rate=self._cfg.tts_rate,
            tts_voice_index=self._cfg.tts_voice_index,
        )

        # --- Tray ---
        self._tray = TrayController(
            on_settings=self._open_settings,
            on_quit=self._quit,
        )

        self._quit_event = threading.Event()

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        # Pre-load models in background so tray appears instantly
        threading.Thread(target=self._preload, daemon=True, name="PreloadThread").start()

        self._tray.start()
        self._wake_engine.start()
        self._capture.start(callback=self._on_audio_chunk)

        logger.info(
            "Ready. Wake word: %r  (lang=%s, wake_model=%s, cmd_model=%s)",
            self._cfg.name, self._cfg.language,
            self._cfg.wake_model, self._cfg.command_model,
        )

        # Block main thread
        self._quit_event.wait()
        self._shutdown()

    # ------------------------------------------------------------------
    # Audio callback (runs in PyAudio thread)
    # ------------------------------------------------------------------

    def _on_audio_chunk(self, chunk: AudioChunk) -> None:
        # Always feed the CommandListener (it ignores data when not armed)
        self._listener.feed(chunk)

        # Only run VAD + WakeWordEngine if listener is not capturing
        if not self._listener.is_armed:
            if self._vad.is_speech(chunk.data):
                speech = SpeechChunk(data=chunk.data, sample_rate=chunk.sample_rate)
                self._wake_engine.feed(speech)

    # ------------------------------------------------------------------
    # Wake word callback
    # ------------------------------------------------------------------

    def _on_wake(self, event: WakeEvent) -> None:
        logger.info("Wake event received: %r", event.transcript)
        self._tray.set_state(TrayState.LISTENING)
        play_sound("wake_ack")
        self._vad.reset()
        self._listener.arm()

    # ------------------------------------------------------------------
    # Command audio callback (called by CommandListener when done)
    # ------------------------------------------------------------------

    def _on_command_audio(self, pcm: bytes) -> None:
        self._tray.set_state(TrayState.PROCESSING)
        event = self._transcriber.transcribe(pcm)

        if not event.text:
            self._dispatcher.dispatch(parse_intent(""))
        else:
            intent = parse_intent(event.text)
            logger.info("Intent: action=%r target=%r", intent.action, intent.target)
            self._dispatcher.dispatch(intent)

        play_sound("command_done")
        self._tray.set_state(TrayState.IDLE)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        from penguin.settings.gui import SettingsWindow
        SettingsWindow(cfg=self._cfg, on_save=self._save_settings).show()

    def _save_settings(self, cfg: AssistantConfig) -> None:
        self._sm.save(cfg)
        logger.info("Settings saved. Restart required for model changes.")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _preload(self) -> None:
        logger.info("Pre-loading STT model in background…")
        self._transcriber.load()
        self._program_index.build(blocking=True)
        logger.info("Pre-load complete.")

    def _quit(self) -> None:
        logger.info("Quit requested.")
        self._quit_event.set()

    def _shutdown(self) -> None:
        logger.info("Shutting down…")
        self._wake_engine.stop()
        self._capture.stop()
        self._tray.stop()
        logger.info("Goodbye.")

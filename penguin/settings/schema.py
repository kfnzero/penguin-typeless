"""Configuration dataclass with default values."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AssistantConfig:
    # Personalisation
    name: str = "小助手"               # Wake word (any language)

    # Wake word detection
    wake_model: str = "tiny"           # faster-whisper model for wake word
    wake_threshold: float = 0.7        # fuzzy-match threshold (0.5–1.0)
    wake_window_seconds: float = 2.0   # audio window fed to tiny Whisper

    # Command recognition
    command_model: str = "small"       # faster-whisper model for commands
    command_capture_seconds: float = 5.0

    # Language (Whisper language hint)
    # "zh" = Chinese, "en" = English, "auto" = auto-detect
    language: str = "zh"

    # Compute
    device: str = "cpu"               # "cpu" or "cuda"
    compute_type: str = "int8"        # int8 fastest on CPU

    # VAD
    vad_threshold: float = 0.5

    # TTS
    tts_rate: int = 180               # words per minute
    tts_voice_index: int = 0          # SAPI5 voice index

    # Startup
    launch_on_startup: bool = False

    # Custom app aliases  {display_name: exe_path}
    custom_apps: dict[str, str] = field(default_factory=dict)

    # Model cache directory (relative to config dir)
    model_dir: str = "models"

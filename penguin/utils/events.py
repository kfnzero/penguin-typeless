from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AudioChunk:
    """Raw PCM audio data from the microphone."""
    data: bytes
    sample_rate: int = 16000
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SpeechChunk:
    """Audio confirmed to contain speech by VAD."""
    data: bytes
    sample_rate: int = 16000
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class WakeEvent:
    """Fired when the wake word is detected."""
    transcript: str
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TranscriptEvent:
    """Result of command transcription."""
    text: str
    language: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CommandEvent:
    """Parsed command ready for dispatch."""
    action: str          # e.g. "open"
    target: str          # e.g. "Chrome"
    raw_text: str
    timestamp: datetime = field(default_factory=datetime.now)

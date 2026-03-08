import logging
import sys
from pathlib import Path


def setup_logging(log_dir: Path | None = None, level: int = logging.INFO) -> None:
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_dir / "penguin.log", encoding="utf-8"))

    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, handlers=handlers)

    # Suppress noisy third-party loggers
    for name in ("faster_whisper", "ctranslate2", "torch"):
        logging.getLogger(name).setLevel(logging.WARNING)

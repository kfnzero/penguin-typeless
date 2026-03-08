#!/usr/bin/env python3
"""Pre-download Whisper models before first run.

Usage:
    python scripts/download_models.py [--model-dir PATH]

By default models are saved to the platform config directory.
"""

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Download faster-whisper models")
    parser.add_argument(
        "--model-dir",
        default=None,
        help="Directory to save models (default: platform config dir)",
    )
    parser.add_argument(
        "--tiny-only", action="store_true",
        help="Download only the tiny model (for wake word detection)",
    )
    args = parser.parse_args()

    if args.model_dir:
        model_dir = Path(args.model_dir)
    else:
        # Use the same logic as SettingsManager
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from penguin.settings.manager import SettingsManager
        model_dir = SettingsManager().model_dir

    model_dir.mkdir(parents=True, exist_ok=True)
    print(f"Model directory: {model_dir}")

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("ERROR: faster-whisper not installed. Run: pip install faster-whisper")
        sys.exit(1)

    models = ["tiny"] if args.tiny_only else ["tiny", "small"]

    for model_name in models:
        print(f"\n{'='*50}")
        print(f"Downloading: faster-whisper {model_name} (multilingual)")
        print(f"{'='*50}")
        try:
            WhisperModel(model_name, device="cpu", compute_type="int8",
                         download_root=str(model_dir))
            print(f"✓ {model_name} downloaded successfully")
        except Exception as exc:
            print(f"✗ Failed to download {model_name}: {exc}")
            sys.exit(1)

    print("\n✓ All models downloaded. You can now run: python -m penguin")


if __name__ == "__main__":
    main()

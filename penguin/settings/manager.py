"""Read/write config.toml from the platform-appropriate config directory."""

from __future__ import annotations

import logging
import sys
import tomllib
from dataclasses import asdict
from pathlib import Path

import tomli_w

from penguin.settings.schema import AssistantConfig

logger = logging.getLogger(__name__)

APP_NAME = "penguin-typeless"


def _config_dir() -> Path:
    if sys.platform == "win32":
        base = Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


class SettingsManager:
    """Manages persistent configuration.

    Example::

        sm = SettingsManager()
        cfg = sm.load()
        cfg.name = "JARVIS"
        sm.save(cfg)
    """

    def __init__(self) -> None:
        self._config_dir = _config_dir()
        self._path = self._config_dir / "config.toml"

    @property
    def config_dir(self) -> Path:
        return self._config_dir

    @property
    def model_dir(self) -> Path:
        d = self._config_dir / "models"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def load(self) -> AssistantConfig:
        if not self._path.exists():
            logger.info("No config found, writing defaults to %s", self._path)
            cfg = AssistantConfig()
            self.save(cfg)
            return cfg

        try:
            with self._path.open("rb") as f:
                data = tomllib.load(f)
        except Exception as exc:
            logger.warning("Failed to read config (%s); using defaults", exc)
            return AssistantConfig()

        cfg = AssistantConfig()
        assistant = data.get("assistant", {})
        for key, val in assistant.items():
            if hasattr(cfg, key):
                setattr(cfg, key, val)

        cfg.custom_apps = data.get("custom_apps", {})
        logger.info("Config loaded from %s", self._path)
        return cfg

    def save(self, cfg: AssistantConfig) -> None:
        d = asdict(cfg)
        custom_apps = d.pop("custom_apps")
        toml_data: dict = {"assistant": d}
        if custom_apps:
            toml_data["custom_apps"] = custom_apps

        try:
            with self._path.open("wb") as f:
                tomli_w.dump(toml_data, f)
            logger.info("Config saved to %s", self._path)
        except Exception as exc:
            logger.error("Failed to save config: %s", exc)

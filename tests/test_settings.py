"""Unit tests for settings manager."""

import sys
from pathlib import Path

import pytest

from penguin.settings.schema import AssistantConfig


def test_defaults():
    cfg = AssistantConfig()
    assert cfg.name == "小助手"
    assert cfg.language == "zh"
    assert cfg.wake_model == "tiny"
    assert cfg.command_model == "small"
    assert cfg.device == "cpu"
    assert cfg.custom_apps == {}


def test_config_mutation():
    cfg = AssistantConfig()
    cfg.name = "JARVIS"
    cfg.language = "en"
    assert cfg.name == "JARVIS"
    assert cfg.language == "en"


def test_settings_manager_roundtrip(tmp_path, monkeypatch):
    """Save and reload config via SettingsManager."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    # Patch config dir resolution
    import penguin.settings.manager as sm_mod
    monkeypatch.setattr(sm_mod, "_config_dir", lambda: tmp_path / "penguin-typeless")

    from penguin.settings.manager import SettingsManager
    sm = SettingsManager()

    cfg = sm.load()   # writes defaults
    cfg.name = "電腦"
    cfg.language = "zh"
    cfg.custom_apps = {"瀏覽器": "chrome.exe"}
    sm.save(cfg)

    cfg2 = sm.load()
    assert cfg2.name == "電腦"
    assert cfg2.language == "zh"
    assert cfg2.custom_apps == {"瀏覽器": "chrome.exe"}

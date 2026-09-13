"""Settings manager for Bangla VoiceTyper.

Handles loading, saving, and merging of configuration settings.
Uses the default config as a fallback and creates a user config
that overrides the defaults.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict


class AppSettings:
    """Class representing application settings."""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get a setting value by section and key."""
        try:
            return self._data.get(section, {}).get(key, default)
        except AttributeError:
            return default

    def set(self, section: str, key: str, value: Any) -> None:
        """Set a setting value by section and key."""
        if section not in self._data:
            self._data[section] = {}
        self._data[section][key] = value

    def get_section(self, section: str) -> Dict[str, Any]:
        """Get an entire section as a dict."""
        return self._data.get(section, {})

    def set_section(self, section: str, values: Dict[str, Any]) -> None:
        """Set an entire section."""
        self._data[section] = values

    def to_dict(self) -> Dict[str, Any]:
        """Return the full settings dict."""
        return self._data

    @property
    def speech_engine(self) -> str:
        return self.get("speech", "engine", "whisper")

    @property
    def whisper_model(self) -> str:
        return self.get("speech", "whisper_model", "small")

    @property
    def language(self) -> str:
        return self.get("speech", "language", "bn")

    @property
    def toggle_hotkey(self) -> str:
        return self.get("hotkey", "toggle", "ctrl+shift+b")

    @property
    def push_to_talk_hotkey(self) -> str:
        return self.get("hotkey", "push_to_talk", "ctrl+b")


class SettingsManager:
    """Manages application settings with persistent storage."""

    CONFIG_DIR_NAME = "BanglaVoiceTyper"
    CONFIG_FILENAME = "config.json"

    def __init__(self):
        self._defaults: Dict[str, Any] = {}
        self._settings: AppSettings | None = None
        self._config_path: Path | None = None
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load default configuration from bundled file."""
        base_dir = Path(__file__).parent
        default_file = base_dir / "default_config.json"
        if default_file.exists():
            try:
                with open(default_file, "r", encoding="utf-8") as f:
                    self._defaults = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._defaults = {}
        else:
            self._defaults = {}

    def _get_config_dir(self) -> Path:
        """Get the user config directory."""
        appdata = os.environ.get("APPDATA", str(Path.home()))
        path = Path(appdata) / self.CONFIG_DIR_NAME
        path.mkdir(parents=True, exist_ok=True)
        return path

    def load(self) -> AppSettings:
        """Load settings, merging user config over defaults."""
        # Start with defaults
        merged: Dict[str, Any] = json.loads(json.dumps(self._defaults))

        # Overlay user config
        self._config_path = self._get_config_dir() / self.CONFIG_FILENAME
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    user_conf = json.load(f)
                self._deep_merge(merged, user_conf)
            except (json.JSONDecodeError, OSError):
                pass  # Use defaults on error

        self._settings = AppSettings(merged)
        return self._settings

    def save(self, settings: AppSettings) -> bool:
        """Save the current settings to disk."""
        try:
            if self._config_path is None:
                self._config_path = self._get_config_dir() / self.CONFIG_FILENAME
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(settings.to_dict(), f, indent=4, ensure_ascii=False)
            return True
        except OSError:
            return False

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """Recursively merge override into base."""
        for key, value in override.items():
            if (
                key in base
                and isinstance(base[key], dict)
                and isinstance(value, dict)
            ):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

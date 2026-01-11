"""
Voice IT - Configuration Management
Handles loading, saving, and accessing application settings.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from platformdirs import user_config_dir, user_data_dir

from voice_it import __app_name__


class Config:
    """
    Configuration manager for Voice IT.
    Stores settings in a YAML file in the user's config directory.
    """

    DEFAULT_CONFIG = {
        # General
        "general": {
            "start_with_os": False,
            "minimize_to_tray": True,
            "show_notifications": True,
            "language": "en",
        },

        # Hotkeys
        "hotkeys": {
            "dictation": {
                "windows": ["ctrl", "win"],
                "linux": ["ctrl", "super"],
                "macos": ["ctrl", "cmd"],
            },
            "command_mode": {
                "windows": ["ctrl", "shift", "win"],
                "linux": ["ctrl", "shift", "super"],
                "macos": ["ctrl", "shift", "cmd"],
            },
        },

        # Audio
        "audio": {
            "microphone": "default",
            "sample_rate": 16000,
            "channels": 1,
            "max_duration_seconds": 300,
        },

        # AI Provider
        "provider": {
            "active": "groq",  # groq, claude, chatgpt, gemini
            "auto_failover": True,
            "connected": {
                "groq": False,
                "claude": False,
                "chatgpt": False,
                "gemini": False,
            },
        },

        # Appearance
        "appearance": {
            "theme": "dark",
            "accent_color": "#00D4AA",
        },

        # Advanced
        "advanced": {
            "debug_mode": False,
            "keep_audio_files": False,
            "auto_update": True,
        },
    }

    def __init__(self):
        """Initialize configuration manager."""
        self._config_dir = Path(user_config_dir(__app_name__))
        self._data_dir = Path(user_data_dir(__app_name__))
        self._config_file = self._config_dir / "config.yaml"
        self._config: Dict[str, Any] = {}

        # Ensure directories exist
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # Load or create config
        self._load()

    def _load(self) -> None:
        """Load configuration from file or create default."""
        if self._config_file.exists():
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f) or {}
                # Merge with defaults (in case new options were added)
                self._config = self._merge_dicts(self.DEFAULT_CONFIG.copy(), loaded)
            except Exception as e:
                print(f"Error loading config: {e}")
                self._config = self.DEFAULT_CONFIG.copy()
        else:
            self._config = self.DEFAULT_CONFIG.copy()
            self._save()

    def _save(self) -> None:
        """Save configuration to file."""
        try:
            with open(self._config_file, "w", encoding="utf-8") as f:
                yaml.dump(self._config, f, default_flow_style=False, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def _merge_dicts(self, base: Dict, override: Dict) -> Dict:
        """Recursively merge override into base dict."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_dicts(result[key], value)
            else:
                result[key] = value
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.

        Args:
            key: Configuration key (e.g., "general.language")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value using dot notation.

        Args:
            key: Configuration key (e.g., "general.language")
            value: Value to set
        """
        keys = key.split(".")
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value
        self._save()

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values."""
        return self._config.copy()

    @property
    def config_dir(self) -> Path:
        """Get the configuration directory path."""
        return self._config_dir

    @property
    def data_dir(self) -> Path:
        """Get the data directory path."""
        return self._data_dir

    @property
    def database_path(self) -> Path:
        """Get the database file path."""
        return self._data_dir / "voice_it.db"

    def reload(self) -> None:
        """Reload configuration from file."""
        self._load()

    def reset(self) -> None:
        """Reset configuration to defaults."""
        self._config = self.DEFAULT_CONFIG.copy()
        self._save()


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        print("[DEBUG] get_config: Creating new Config instance")
        _config = Config()
        print(f"[DEBUG] get_config: Config id={id(_config)}")
    else:
        print(f"[DEBUG] get_config: Returning existing Config id={id(_config)}")
    return _config

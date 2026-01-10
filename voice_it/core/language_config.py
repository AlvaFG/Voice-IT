"""
Voice IT - Language Configuration
Handles language settings for transcription.
"""

from dataclasses import dataclass, field
from typing import Optional


# Supported languages for Whisper transcription
SUPPORTED_LANGUAGES = {
    "auto": "Auto-detect",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
    "hi": "Hindi",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
    "ms": "Malay",
    "sv": "Swedish",
    "da": "Danish",
    "no": "Norwegian",
    "fi": "Finnish",
    "cs": "Czech",
    "sk": "Slovak",
    "uk": "Ukrainian",
    "el": "Greek",
    "he": "Hebrew",
    "ro": "Romanian",
    "hu": "Hungarian",
    "bg": "Bulgarian",
    "hr": "Croatian",
    "sr": "Serbian",
    "sl": "Slovenian",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "et": "Estonian",
    "ca": "Catalan",
    "gl": "Galician",
    "eu": "Basque",
}


@dataclass
class LanguageConfig:
    """Configuration for language settings."""

    language: str = "auto"
    """Language code for transcription (e.g., 'en', 'es', 'auto')."""

    translate_to_english: bool = False
    """Whether to translate non-English speech to English."""

    prompt: Optional[str] = None
    """Optional prompt to guide transcription style/vocabulary."""

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.language not in SUPPORTED_LANGUAGES:
            self.language = "auto"

    def get_language_name(self) -> str:
        """Get human-readable language name."""
        return SUPPORTED_LANGUAGES.get(self.language, "Auto-detect")

    def is_auto_detect(self) -> bool:
        """Check if using auto-detection."""
        return self.language == "auto"


# Global instance
_language_config: Optional[LanguageConfig] = None


def get_language_config() -> LanguageConfig:
    """Get the global language configuration instance."""
    global _language_config
    if _language_config is None:
        _language_config = LanguageConfig()
    return _language_config


def inject_language_config(config: LanguageConfig) -> None:
    """Inject a custom language configuration (for testing/customization)."""
    global _language_config
    _language_config = config


def get_supported_languages() -> dict[str, str]:
    """Get dictionary of supported language codes and names."""
    return SUPPORTED_LANGUAGES.copy()

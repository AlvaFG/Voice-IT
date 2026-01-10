"""Voice IT - Core modules"""

from voice_it.core.audio_engine import AudioEngine
from voice_it.core.hotkey_manager import HotkeyManager
from voice_it.core.paste_handler import PasteHandler, get_paste_handler
from voice_it.core.context_detector import (
    ContextDetector,
    AppContext,
    get_context_detector,
    get_current_app_context,
)
from voice_it.core.language_config import (
    LanguageConfig,
    get_language_config,
    get_supported_languages,
    inject_language_config,
)
from voice_it.core.retry import (
    RetryError,
    async_retry,
    calculate_backoff,
    retry,
    retry_async_operation,
)

__all__ = [
    "AudioEngine",
    "HotkeyManager",
    "PasteHandler",
    "get_paste_handler",
    "ContextDetector",
    "AppContext",
    "get_context_detector",
    "get_current_app_context",
    "LanguageConfig",
    "get_language_config",
    "get_supported_languages",
    "inject_language_config",
    "RetryError",
    "async_retry",
    "calculate_backoff",
    "retry",
    "retry_async_operation",
]

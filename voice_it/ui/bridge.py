"""
Voice IT - PyWebView Bridge
Exposes Python backend functionality to JavaScript via PyWebView's JS API.
"""

import threading
from typing import Any, Callable, Dict, List, Optional

from voice_it import __app_name__, __version__
from voice_it.storage.config import get_config
from voice_it.storage.database import get_database
from voice_it.core.paste_handler import get_paste_handler
from voice_it.providers import get_provider_manager, run_async


class VoiceITAPI:
    """
    PyWebView JS API bridge.
    All public methods are exposed to JavaScript via window.pywebview.api
    """

    def __init__(self, callbacks: Optional[Dict[str, Callable]] = None):
        """
        Initialize the API bridge.

        Args:
            callbacks: Optional dict of callback functions for app control
                - on_minimize: Called when minimize to tray requested
                - on_quit: Called when quit requested
                - on_provider_change: Called when active provider changes
        """
        self._config = get_config()
        self._db = get_database()
        self._paste_handler = get_paste_handler()
        self._provider_manager = get_provider_manager()
        self._callbacks = callbacks or {}
        self._window = None  # Set by WindowManager

    def set_window(self, window):
        """Set the pywebview window reference for evaluate_js calls."""
        self._window = window

    # =========================================================================
    # APP INFO
    # =========================================================================

    def get_app_info(self) -> Dict[str, Any]:
        """Get application information."""
        import platform
        return {
            "name": __app_name__,
            "version": __version__,
            "platform": platform.system(),
        }

    # =========================================================================
    # CONFIGURATION
    # =========================================================================

    def get_config(self, key: str) -> Any:
        """Get a configuration value."""
        return self._config.get(key)

    def set_config(self, key: str, value: Any) -> bool:
        """Set a configuration value."""
        try:
            self._config.set(key, value)
            return True
        except Exception as e:
            print(f"Error setting config {key}: {e}")
            return False

    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration values."""
        return self._config.get_all()

    # =========================================================================
    # PROVIDERS
    # =========================================================================

    def get_providers_status(self) -> Dict[str, Any]:
        """
        Get status of all AI providers.

        Returns:
            Dict with provider statuses and active provider
        """
        connected = self._provider_manager.get_connected_providers()
        active = self._provider_manager.active_provider_name

        return {
            "providers": {
                "groq": {
                    "id": "groq",
                    "name": "Groq (Whisper)",
                    "connected": "groq" in connected,
                    "requires_api_key": True,
                },
                "chatgpt": {
                    "id": "chatgpt",
                    "name": "ChatGPT",
                    "connected": "chatgpt" in connected,
                    "requires_api_key": True,
                },
                "gemini": {
                    "id": "gemini",
                    "name": "Gemini",
                    "connected": "gemini" in connected,
                    "requires_api_key": True,
                },
                "grok": {
                    "id": "grok",
                    "name": "Grok (xAI)",
                    "connected": "grok" in connected,
                    "requires_api_key": True,
                },
            },
            "active": active,
        }

    def connect_provider(self, provider_id: str) -> Dict[str, Any]:
        """
        Start async connection to a provider.
        Result will be sent via evaluate_js callback.

        Args:
            provider_id: Provider ID (claude, chatgpt, gemini)

        Returns:
            Initial status response
        """
        def do_connect():
            try:
                success = run_async(self._provider_manager.authenticate(provider_id))
                if self._window:
                    self._window.evaluate_js(
                        f"App.onProviderConnected('{provider_id}', {str(success).lower()})"
                    )
                if success and self._callbacks.get("on_provider_change"):
                    self._callbacks["on_provider_change"](provider_id, True)
            except Exception as e:
                print(f"Error connecting to {provider_id}: {e}")
                if self._window:
                    self._window.evaluate_js(
                        f"App.onProviderError('{provider_id}', '{str(e)}')"
                    )

        threading.Thread(target=do_connect, daemon=True).start()
        return {"status": "connecting", "provider": provider_id}

    def disconnect_provider(self, provider_id: str) -> Dict[str, Any]:
        """
        Disconnect from a provider.

        Args:
            provider_id: Provider ID

        Returns:
            Result dict with success status
        """
        try:
            success = run_async(self._provider_manager.disconnect(provider_id))
            if success and self._callbacks.get("on_provider_change"):
                self._callbacks["on_provider_change"](provider_id, False)
            return {"success": success}
        except Exception as e:
            print(f"Error disconnecting from {provider_id}: {e}")
            return {"success": False, "error": str(e)}

    def set_active_provider(self, provider_id: str) -> bool:
        """Set the active provider for transcription."""
        try:
            self._provider_manager.active_provider_name = provider_id
            self._config.set("providers.active", provider_id)
            return True
        except Exception as e:
            print(f"Error setting active provider: {e}")
            return False

    def connect_provider_with_key(self, provider_id: str, api_key: str) -> Dict[str, Any]:
        """
        Connect a provider using an API key.

        Args:
            provider_id: Provider ID (e.g., "groq")
            api_key: The API key for authentication

        Returns:
            Initial status response
        """
        from voice_it.storage.auth_store import get_auth_store

        def do_connect():
            try:
                # Save the API key
                auth_store = get_auth_store()
                auth_store.save_token(provider_id, "api_key", api_key)

                # Update config to mark as connected
                self._config.set(f"provider.connected.{provider_id}", True)

                # Notify UI of success
                if self._window:
                    self._window.evaluate_js(
                        f"App.onProviderConnected('{provider_id}', true)"
                    )

                if self._callbacks.get("on_provider_change"):
                    self._callbacks["on_provider_change"](provider_id, True)

            except Exception as e:
                print(f"Error connecting {provider_id} with API key: {e}")
                if self._window:
                    self._window.evaluate_js(
                        f"App.onProviderError('{provider_id}', '{str(e)}')"
                    )

        threading.Thread(target=do_connect, daemon=True).start()
        return {"status": "connecting", "provider": provider_id}

    # =========================================================================
    # HISTORY
    # =========================================================================

    def get_history(
        self, limit: int = 50, offset: int = 0, search: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Get transcription history.

        Args:
            limit: Maximum entries to return
            offset: Offset for pagination
            search: Search query to filter results

        Returns:
            List of history entries
        """
        return self._db.get_history(limit, offset, search if search else None)

    def delete_history_entry(self, entry_id: int) -> bool:
        """Delete a single history entry."""
        return self._db.delete_history(entry_id)

    def clear_all_history(self) -> bool:
        """Clear all history entries."""
        return self._db.clear_history()

    # =========================================================================
    # CLIPBOARD
    # =========================================================================

    def copy_to_clipboard(self, text: str) -> bool:
        """Copy text to clipboard."""
        return self._paste_handler.copy_to_clipboard(text)

    def paste_text(self, text: str) -> bool:
        """Paste text to active application."""
        return self._paste_handler.paste_text(text)

    def get_clipboard(self) -> Optional[str]:
        """Get current clipboard contents."""
        return self._paste_handler.get_clipboard()

    # =========================================================================
    # APP CONTROL
    # =========================================================================

    def minimize_to_tray(self) -> None:
        """Minimize window to system tray."""
        if self._callbacks.get("on_minimize"):
            self._callbacks["on_minimize"]()

    def quit_app(self) -> None:
        """Quit the application."""
        if self._callbacks.get("on_quit"):
            self._callbacks["on_quit"]()

    # =========================================================================
    # HOTKEY CONFIGURATION
    # =========================================================================

    def get_hotkey_config(self) -> Dict[str, Any]:
        """Get current hotkey configuration."""
        import platform

        # Determine platform key
        system = platform.system().lower()
        if system == "windows":
            platform_key = "windows"
        elif system == "darwin":
            platform_key = "macos"
        else:
            platform_key = "linux"

        # Get hotkeys for current platform
        dictation_config = self._config.get("hotkeys.dictation", {})
        command_config = self._config.get("hotkeys.command_mode", {})

        # Handle both dict (platform-specific) and list (flat) formats
        if isinstance(dictation_config, dict):
            dictation = dictation_config.get(platform_key, ["ctrl", "win"])
        else:
            dictation = dictation_config if isinstance(dictation_config, list) else ["ctrl", "win"]

        if isinstance(command_config, dict):
            command_mode = command_config.get(platform_key, ["ctrl", "shift", "win"])
        else:
            command_mode = command_config if isinstance(command_config, list) else ["ctrl", "shift", "win"]

        return {
            "dictation": dictation,
            "command_mode": command_mode,
        }

    def set_hotkey(self, mode: str, keys: List[str]) -> bool:
        """
        Set hotkey for a mode.

        Args:
            mode: Hotkey mode (dictation or command_mode)
            keys: List of key names

        Returns:
            Success status
        """
        try:
            self._config.set(f"hotkeys.{mode}", keys)
            return True
        except Exception as e:
            print(f"Error setting hotkey: {e}")
            return False

    # =========================================================================
    # LANGUAGE
    # =========================================================================

    def get_language(self) -> str:
        """Get current language setting."""
        return self._config.get("general.language", "en")

    def set_language(self, language: str) -> bool:
        """Set language for transcription."""
        try:
            self._config.set("general.language", language)
            return True
        except Exception as e:
            print(f"Error setting language: {e}")
            return False

    def get_supported_languages(self) -> List[Dict[str, str]]:
        """Get list of supported languages."""
        return [
            {"code": "en", "name": "English"},
            {"code": "es", "name": "Spanish"},
            {"code": "fr", "name": "French"},
            {"code": "de", "name": "German"},
            {"code": "pt", "name": "Portuguese"},
            {"code": "it", "name": "Italian"},
            {"code": "zh", "name": "Chinese"},
            {"code": "ja", "name": "Japanese"},
        ]

    # =========================================================================
    # STARTUP SETTINGS
    # =========================================================================

    def is_startup_enabled(self) -> bool:
        """Check if the application is set to start with Windows."""
        from voice_it.core.startup import is_startup_enabled
        return is_startup_enabled()

    def set_startup_enabled(self, enabled: bool) -> bool:
        """
        Enable or disable auto-start with Windows.

        Args:
            enabled: True to enable, False to disable.

        Returns:
            True if successful, False otherwise.
        """
        from voice_it.core.startup import set_startup_enabled as set_startup
        try:
            # Always start minimized when auto-starting with Windows
            success = set_startup(enabled, start_minimized=True)
            if success:
                self._config.set("general.start_with_os", enabled)
            return success
        except Exception as e:
            print(f"Error setting startup: {e}")
            return False

"""
Voice IT - Provider Manager
Orchestrates AI providers with automatic failover support.
"""

import asyncio
from typing import Callable, Dict, List, Optional

from voice_it.providers.base_provider import (
    BaseProvider,
    ProviderStatus,
    TranscriptionResult,
    TransformResult,
)
from voice_it.providers.chatgpt_provider import ChatGPTAdapter
from voice_it.providers.gemini_provider import GeminiAdapter
from voice_it.providers.groq_provider import GroqProvider
from voice_it.providers.grok_provider import GrokProvider
from voice_it.storage.auth_store import AuthStore, get_auth_store
from voice_it.storage.config import Config, get_config


class ProviderManager:
    """
    Manages multiple AI providers with automatic failover.
    """

    # Provider order for failover (groq first - fastest)
    PROVIDER_ORDER = ["groq", "chatgpt", "gemini", "grok"]

    def __init__(
        self,
        config: Optional[Config] = None,
        auth_store: Optional[AuthStore] = None,
    ):
        """
        Initialize the provider manager.

        Args:
            config: Application configuration (uses global if not provided)
            auth_store: Authentication store (uses global if not provided)
        """
        self.config = config or get_config()
        self.auth_store = auth_store or get_auth_store()

        # Initialize providers (lazy loading)
        self._providers: Dict[str, BaseProvider] = {}
        self._status_callback: Optional[Callable[[str, ProviderStatus], None]] = None
        self._notification_callback: Optional[Callable[[str, str, str], None]] = None

    def _get_provider(self, name: str) -> Optional[BaseProvider]:
        """
        Get or create a provider instance.

        Args:
            name: Provider name ("claude", "chatgpt", "gemini")

        Returns:
            Provider instance or None if not supported or dependencies missing
        """
        if name in self._providers:
            return self._providers[name]

        provider = None

        try:
            if name == "groq":
                provider = GroqProvider(self.auth_store, self.config)
            elif name == "chatgpt":
                provider = ChatGPTAdapter(self.auth_store, self.config)
            elif name == "gemini":
                provider = GeminiAdapter(self.auth_store, self.config)
            elif name == "grok":
                provider = GrokProvider(self.auth_store, self.config)
        except ImportError as e:
            print(f"[WARNING] Provider '{name}' unavailable: {e}")
            self._unavailable_providers = getattr(self, '_unavailable_providers', set())
            self._unavailable_providers.add(name)
            return None

        if provider:
            # Set up status callback forwarding
            if self._status_callback:
                provider.set_status_callback(
                    lambda status, n=name: self._status_callback(n, status)
                )
            self._providers[name] = provider

        return provider

    def set_status_callback(
        self,
        callback: Callable[[str, ProviderStatus], None],
    ):
        """
        Set a callback for provider status changes.

        Args:
            callback: Function(provider_name, status) to call on status changes
        """
        self._status_callback = callback

        # Update existing providers
        for name, provider in self._providers.items():
            provider.set_status_callback(
                lambda status, n=name: self._status_callback(n, status)
            )

    def set_notification_callback(
        self,
        callback: Callable[[str, str, str], None],
    ):
        """
        Set a callback for notifications (e.g., failover events).

        Args:
            callback: Function(title, message, level) where level is 'info', 'warning', 'error'
        """
        self._notification_callback = callback

    def _notify(self, title: str, message: str, level: str = "info"):
        """Send a notification if callback is set."""
        if self._notification_callback:
            self._notification_callback(title, message, level)

    @property
    def active_provider_name(self) -> str:
        """Get the name of the currently active provider."""
        stored = self.config.get("provider.active", "groq")
        # Validate that the stored provider is valid
        if stored not in self.PROVIDER_ORDER:
            # Reset to default if invalid (e.g., "claude" is no longer valid)
            self.config.set("provider.active", "groq")
            return "groq"
        return stored

    @active_provider_name.setter
    def active_provider_name(self, value: str):
        """Set the active provider."""
        if value in self.PROVIDER_ORDER:
            self.config.set("provider.active", value)

    @property
    def active_provider(self) -> Optional[BaseProvider]:
        """Get the currently active provider instance."""
        return self._get_provider(self.active_provider_name)

    def get_connected_providers(self) -> List[str]:
        """Get list of connected provider names."""
        connected = []
        for name in self.PROVIDER_ORDER:
            provider = self._get_provider(name)
            if provider is None:
                continue

            # Check actual credentials (cookie file exists)
            has_credentials = provider.is_authenticated()

            # Check in-memory status
            provider_status_connected = provider.status == ProviderStatus.CONNECTED

            # Config flag (for UI display, but not sufficient alone)
            config_connected = self.config.get(f"provider.connected.{name}", False)

            # REQUIRE actual credentials OR active session to be considered connected
            # Config flag alone is NOT sufficient
            if has_credentials or provider_status_connected:
                connected.append(name)
                # Sync config
                if not config_connected:
                    self.config.set(f"provider.connected.{name}", True)
            else:
                # Clear stale config flag if no actual credentials
                if config_connected:
                    self.config.set(f"provider.connected.{name}", False)

        return connected

    def is_any_connected(self) -> bool:
        """Check if any provider is connected."""
        return len(self.get_connected_providers()) > 0

    async def authenticate(self, provider_name: str) -> bool:
        """
        Authenticate with a specific provider.

        Args:
            provider_name: Provider to authenticate

        Returns:
            True if successful, False otherwise
        """
        provider = self._get_provider(provider_name)
        if provider is None:
            print(f"Unknown provider: {provider_name}")
            return False

        return await provider.authenticate()

    async def disconnect(self, provider_name: str) -> bool:
        """
        Disconnect a specific provider.

        Args:
            provider_name: Provider to disconnect

        Returns:
            True if successful, False otherwise
        """
        provider = self._get_provider(provider_name)
        if provider is None:
            return False

        return provider.disconnect()

    async def transcribe(
        self,
        audio_data: bytes,
        prompt: Optional[str] = None,
        language: str = "en",
    ) -> TranscriptionResult:
        """
        Transcribe audio using the active provider with optional failover.

        Args:
            audio_data: WAV audio bytes
            prompt: Optional transcription prompt
            language: Language code

        Returns:
            TranscriptionResult with transcribed text
        """
        # Try active provider first
        active = self.active_provider

        if active:
            if active.is_authenticated():
                result = await active.transcribe(audio_data, prompt, language)
                if result.success:
                    return result

                # Check if we should try failover
                if not self.config.get("provider.auto_failover", True):
                    return result

        # Try other connected providers (failover)
        if self.config.get("provider.auto_failover", True):
            for provider_name in self.PROVIDER_ORDER:
                if provider_name == self.active_provider_name:
                    continue

                provider = self._get_provider(provider_name)
                if provider and provider.is_authenticated():
                    self._notify(
                        "Provider Failover",
                        f"Switching to {provider.DISPLAY_NAME} due to {self.active_provider_name} failure",
                        "warning"
                    )
                    result = await provider.transcribe(audio_data, prompt, language)
                    if result.success:
                        self._notify(
                            "Failover Success",
                            f"Transcription completed using {provider.DISPLAY_NAME}",
                            "info"
                        )
                        return result

        # No provider succeeded
        return TranscriptionResult(
            text="",
            error="No connected providers available. Please connect a provider first.",
        )

    async def transform(
        self,
        text: str,
        command: str,
        context: Optional[str] = None,
    ) -> TransformResult:
        """
        Transform text using the active provider with optional failover.

        Args:
            text: Text to transform
            command: Transformation command
            context: Optional context

        Returns:
            TransformResult with transformed text
        """
        # Try active provider first
        active = self.active_provider
        if active and active.is_authenticated():
            result = await active.transform(text, command, context)
            if result.success:
                return result

        # Try failover
        if self.config.get("provider.auto_failover", True):
            for provider_name in self.PROVIDER_ORDER:
                if provider_name == self.active_provider_name:
                    continue

                provider = self._get_provider(provider_name)
                if provider and provider.is_authenticated():
                    self._notify(
                        "Provider Failover",
                        f"Switching to {provider.DISPLAY_NAME} for transformation",
                        "warning"
                    )
                    result = await provider.transform(text, command, context)
                    if result.success:
                        return result

        self._notify(
            "All Providers Failed",
            "No connected providers could complete the request",
            "error"
        )
        return TransformResult(
            text="",
            original_text=text,
            command=command,
            error="No connected providers available.",
        )

    async def validate_all_sessions(self) -> Dict[str, bool]:
        """
        Validate all connected provider sessions.

        Returns:
            Dict mapping provider name to validity status
        """
        results = {}
        for provider_name in self.get_connected_providers():
            provider = self._get_provider(provider_name)
            if provider:
                results[provider_name] = await provider.validate_session()
        return results

    def get_provider_status(self, provider_name: str) -> ProviderStatus:
        """
        Get the status of a specific provider.

        Args:
            provider_name: Provider to check

        Returns:
            ProviderStatus enum value
        """
        provider = self._get_provider(provider_name)
        if provider:
            return provider.status

        # Check if connected in config
        if self.config.get(f"provider.connected.{provider_name}", False):
            return ProviderStatus.CONNECTED

        return ProviderStatus.DISCONNECTED


# Global provider manager instance
_provider_manager: Optional[ProviderManager] = None


def get_provider_manager() -> ProviderManager:
    """Get the global provider manager instance."""
    global _provider_manager
    if _provider_manager is None:
        _provider_manager = ProviderManager()
    return _provider_manager


# Convenience function for synchronous code
def run_async(coro):
    """Run an async coroutine from synchronous code."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coro)

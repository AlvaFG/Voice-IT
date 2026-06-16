"""
Voice IT - Base Provider Interface
Abstract base class for all AI provider adapters.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from voice_it.storage.auth_store import AuthStore
from voice_it.storage.config import Config

# Network safety defaults shared by the HTTP/SDK-based providers: cap how long
# an API call can hang, with a couple of automatic retries (handled natively by
# the Groq/OpenAI SDKs).
API_TIMEOUT = 30.0
API_MAX_RETRIES = 2


class ProviderStatus(Enum):
    """Status of a provider connection."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class TranscriptionResult:
    """Result of a transcription request."""
    text: str
    raw_text: Optional[str] = None
    confidence: Optional[float] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Check if transcription was successful."""
        return self.error is None and self.text is not None


@dataclass
class TransformResult:
    """Result of a text transformation request."""
    text: str
    original_text: str
    command: str
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Check if transformation was successful."""
        return self.error is None and self.text is not None


class BaseProvider(ABC):
    """
    Abstract base class for AI provider adapters.
    All providers (Claude, ChatGPT, Gemini) must implement this interface.
    """

    # Provider identification
    PROVIDER_NAME: str = "base"
    DISPLAY_NAME: str = "Base Provider"

    def __init__(self, auth_store: AuthStore, config: Config):
        """
        Initialize the provider.

        Args:
            auth_store: Authentication store for credentials
            config: Application configuration
        """
        self.auth_store = auth_store
        self.config = config
        self._status = ProviderStatus.DISCONNECTED
        self._status_callback: Optional[Callable[[ProviderStatus], None]] = None

    @property
    def status(self) -> ProviderStatus:
        """Get the current connection status."""
        return self._status

    @status.setter
    def status(self, value: ProviderStatus):
        """Set the connection status and notify callback."""
        self._status = value
        if self._status_callback:
            self._status_callback(value)

    def set_status_callback(self, callback: Callable[[ProviderStatus], None]):
        """Set a callback for status changes."""
        self._status_callback = callback

    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Perform OAuth authentication flow.
        Opens browser for user login, captures session, stores credentials.

        Returns:
            True if authentication successful, False otherwise
        """
        pass

    @abstractmethod
    async def transcribe(
        self,
        audio_data: bytes,
        prompt: Optional[str] = None,
        language: str = "en",
    ) -> TranscriptionResult:
        """
        Transcribe audio to text.

        Args:
            audio_data: Audio bytes (WAV format)
            prompt: Optional transcription prompt/instructions
            language: Language code (default: "en")

        Returns:
            TranscriptionResult with transcribed text or error
        """
        pass

    @abstractmethod
    async def transform(
        self,
        text: str,
        command: str,
        context: Optional[str] = None,
    ) -> TransformResult:
        """
        Transform text based on a command.

        Args:
            text: Text to transform
            command: Transformation command (e.g., "make formal", "fix grammar")
            context: Optional context for the transformation

        Returns:
            TransformResult with transformed text or error
        """
        pass

    @abstractmethod
    def is_authenticated(self) -> bool:
        """
        Check if provider has valid credentials.

        Returns:
            True if authenticated, False otherwise
        """
        pass

    @abstractmethod
    async def validate_session(self) -> bool:
        """
        Validate that the current session is still valid.

        Returns:
            True if session is valid, False otherwise
        """
        pass

    @abstractmethod
    async def refresh_auth(self) -> bool:
        """
        Refresh credentials if needed.

        Returns:
            True if refresh successful or not needed, False otherwise
        """
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """
        Disconnect and clear stored credentials.

        Returns:
            True if successful, False otherwise
        """
        pass

    def get_prompt(self, prompt_name: str) -> Optional[str]:
        """
        Load a prompt template from the prompts directory.

        Args:
            prompt_name: Name of the prompt file (without .md extension)

        Returns:
            Prompt content or None if not found
        """
        from pathlib import Path

        prompt_file = Path(__file__).parent.parent / "prompts" / f"{prompt_name}.md"
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8")
        return None

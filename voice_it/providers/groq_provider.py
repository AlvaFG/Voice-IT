"""
Voice IT - Groq Provider
Uses Groq's Whisper API for fast, reliable speech-to-text transcription.
"""

import io
import time
from typing import Optional

try:
    from groq import Groq
except ImportError:
    Groq = None

from voice_it.providers.base_provider import (
    API_MAX_RETRIES,
    API_TIMEOUT,
    BaseProvider,
    ProviderStatus,
    TranscriptionResult,
    TransformResult,
)
from voice_it.storage.auth_store import AuthStore
from voice_it.storage.config import Config


class GroqProvider(BaseProvider):
    """
    Groq provider using Whisper API for transcription.

    Groq offers extremely fast inference using their LPU (Language Processing Unit)
    hardware, making it ideal for real-time transcription.
    """

    PROVIDER_NAME = "groq"
    DISPLAY_NAME = "Groq (Whisper)"

    # Groq Whisper model
    WHISPER_MODEL = "whisper-large-v3"

    # Groq LLM for text transformation (optional)
    LLM_MODEL = "llama-3.1-70b-versatile"

    def __init__(self, auth_store: AuthStore, config: Config):
        """
        Initialize the Groq provider.

        Args:
            auth_store: Authentication store for API key
            config: Application configuration
        """
        if Groq is None:
            raise ImportError(
                "groq not installed. Run: pip install groq"
            )

        super().__init__(auth_store, config)
        self._client: Optional[Groq] = None
        self._api_key: Optional[str] = None

        # Try to load existing API key
        self._load_api_key()

    def _load_api_key(self):
        """Load API key from storage."""
        api_key = self.auth_store.get_token(self.PROVIDER_NAME, "api_key")
        if api_key:
            self._api_key = api_key
            self._client = Groq(api_key=api_key, timeout=API_TIMEOUT, max_retries=API_MAX_RETRIES)

    def _get_client(self) -> Optional[Groq]:
        """Get or create Groq client."""
        if self._client is None and self._api_key:
            self._client = Groq(api_key=self._api_key, timeout=API_TIMEOUT, max_retries=API_MAX_RETRIES)
        return self._client

    async def authenticate(self, api_key: str = None) -> bool:
        """
        Authenticate with Groq using an API key.

        Args:
            api_key: Groq API key (if not provided, uses stored key)

        Returns:
            True if authentication successful, False otherwise
        """
        self.status = ProviderStatus.CONNECTING

        try:
            # Use provided key or try to load from storage
            if api_key:
                self._api_key = api_key
            elif not self._api_key:
                stored_key = self.auth_store.get_token(self.PROVIDER_NAME, "api_key")
                if stored_key:
                    self._api_key = stored_key

            if not self._api_key:
                print("[ERROR] GroqProvider: No API key provided")
                self.status = ProviderStatus.ERROR
                return False

            # Create client and validate
            self._client = Groq(api_key=self._api_key, timeout=API_TIMEOUT, max_retries=API_MAX_RETRIES)

            # Test the API key with a simple request
            # Using models.list() as a lightweight validation
            try:
                self._client.models.list()
            except Exception as e:
                print(f"[ERROR] GroqProvider: Invalid API key - {e}")
                self._api_key = None
                self._client = None
                self.status = ProviderStatus.ERROR
                return False

            # Save the API key
            if api_key:  # Only save if a new key was provided
                self.auth_store.save_token(self.PROVIDER_NAME, "api_key", api_key)

            # Update config
            self.config.set(f"provider.connected.{self.PROVIDER_NAME}", True)

            self.status = ProviderStatus.CONNECTED
            return True

        except Exception as e:
            print(f"[ERROR] GroqProvider.authenticate: {e}")
            self.status = ProviderStatus.ERROR
            return False

    async def transcribe(
        self,
        audio_data: bytes,
        prompt: Optional[str] = None,
        language: str = "en",
    ) -> TranscriptionResult:
        """
        Transcribe audio using Groq Whisper API.

        Args:
            audio_data: Audio bytes (WAV format)
            prompt: Optional transcription prompt (not used by Whisper)
            language: Language code (default: "en")

        Returns:
            TranscriptionResult with transcribed text or error
        """
        start_time = time.time()

        try:
            client = self._get_client()
            if not client:
                return TranscriptionResult(
                    text="",
                    error="Not authenticated. Please connect Groq first.",
                )

            # Create file-like object from bytes
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "audio.wav"

            # Call Groq Whisper API
            # Don't specify language to let Whisper auto-detect
            # This prevents forced translation when user speaks different languages
            transcription = client.audio.transcriptions.create(
                model=self.WHISPER_MODEL,
                file=audio_file,
                response_format="text",
            )

            duration_ms = int((time.time() - start_time) * 1000)

            # transcription is already a string when response_format="text"
            text = transcription if isinstance(transcription, str) else transcription.text

            return TranscriptionResult(
                text=text.strip(),
                raw_text=text,
                duration_ms=duration_ms,
            )

        except Exception as e:
            error_str = str(e).lower()
            print(f"[ERROR] GroqProvider.transcribe: {e}")

            # Detect rate limit error
            if "rate_limit" in error_str or "429" in error_str or "rate limit" in error_str:
                return TranscriptionResult(
                    text="",
                    error="Llegaste al límite de Groq. El límite se reinicia en unos minutos. Conectá otro provider (Gemini es gratis) o esperá un momento.",
                )

            return TranscriptionResult(
                text="",
                error=str(e),
            )

    async def transform(
        self,
        text: str,
        command: str,
        context: Optional[str] = None,
    ) -> TransformResult:
        """
        Transform text using Groq LLM.

        Args:
            text: Text to transform
            command: Transformation command (e.g., "make formal", "fix grammar")
            context: Optional context for the transformation

        Returns:
            TransformResult with transformed text or error
        """
        try:
            client = self._get_client()
            if not client:
                return TransformResult(
                    text="",
                    original_text=text,
                    command=command,
                    error="Not authenticated. Please connect Groq first.",
                )

            # Build the prompt
            system_prompt = "You are a text transformation assistant. Transform the given text according to the user's command. Return ONLY the transformed text, nothing else."

            user_prompt = f"Command: {command}\n\nText to transform:\n{text}"
            if context:
                user_prompt += f"\n\nContext: {context}"

            # Call Groq LLM
            response = client.chat.completions.create(
                model=self.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
            )

            transformed_text = response.choices[0].message.content.strip()

            return TransformResult(
                text=transformed_text,
                original_text=text,
                command=command,
            )

        except Exception as e:
            error_str = str(e).lower()
            print(f"[ERROR] GroqProvider.transform: {e}")

            # Detect rate limit error
            if "rate_limit" in error_str or "429" in error_str or "rate limit" in error_str:
                return TransformResult(
                    text="",
                    original_text=text,
                    command=command,
                    error="Llegaste al límite de Groq. El límite se reinicia en unos minutos.",
                )

            return TransformResult(
                text="",
                original_text=text,
                command=command,
                error=str(e),
            )

    def is_authenticated(self) -> bool:
        """
        Check if Groq API key exists.

        Returns:
            True if authenticated, False otherwise
        """
        # Check in-memory first
        if self._api_key:
            return True

        # Check storage
        stored_key = self.auth_store.get_token(self.PROVIDER_NAME, "api_key")
        if stored_key:
            self._api_key = stored_key
            self._client = Groq(api_key=stored_key, timeout=API_TIMEOUT, max_retries=API_MAX_RETRIES)
            return True

        return False

    async def validate_session(self) -> bool:
        """
        Validate that the API key is still working.

        Returns:
            True if session is valid, False otherwise
        """
        if not self._api_key:
            return False

        try:
            client = self._get_client()
            if not client:
                return False

            # Test with a simple API call
            client.models.list()
            return True

        except Exception:
            return False

    async def refresh_auth(self) -> bool:
        """
        API keys don't expire, so just validate.

        Returns:
            True if key is valid, False otherwise
        """
        return await self.validate_session()

    def disconnect(self) -> bool:
        """
        Disconnect and clear stored API key.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Clear in-memory state
            self._api_key = None
            self._client = None

            # Clear stored key
            self.auth_store.delete_token(self.PROVIDER_NAME, "api_key")

            # Update config
            self.config.set(f"provider.connected.{self.PROVIDER_NAME}", False)

            self.status = ProviderStatus.DISCONNECTED
            return True

        except Exception as e:
            print(f"[ERROR] GroqProvider.disconnect: {e}")
            return False

"""
Voice IT - Grok Provider
Uses xAI's Grok API for speech-to-text transcription and text transformation.
"""

import io
import time
from typing import Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

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


class GrokProvider(BaseProvider):
    """
    Grok provider using xAI's API for transcription and text transformation.

    xAI's API is OpenAI-compatible, so we use the OpenAI client with a custom base URL.
    """

    PROVIDER_NAME = "grok"
    DISPLAY_NAME = "Grok (xAI)"

    # xAI API endpoint
    BASE_URL = "https://api.x.ai/v1"

    # Grok models
    CHAT_MODEL = "grok-beta"

    def __init__(self, auth_store: AuthStore, config: Config):
        """
        Initialize the Grok provider.

        Args:
            auth_store: Authentication store for API key
            config: Application configuration
        """
        if OpenAI is None:
            raise ImportError(
                "openai not installed. Run: pip install openai"
            )

        super().__init__(auth_store, config)
        self._client: Optional[OpenAI] = None
        self._api_key: Optional[str] = None

        # Try to load existing API key
        self._load_api_key()

    def _load_api_key(self):
        """Load API key from storage."""
        api_key = self.auth_store.get_token(self.PROVIDER_NAME, "api_key")
        if api_key:
            self._api_key = api_key
            self._client = OpenAI(api_key=api_key, base_url=self.BASE_URL, timeout=API_TIMEOUT, max_retries=API_MAX_RETRIES)

    def _get_client(self) -> Optional[OpenAI]:
        """Get or create OpenAI client for xAI."""
        if self._client is None and self._api_key:
            self._client = OpenAI(api_key=self._api_key, base_url=self.BASE_URL, timeout=API_TIMEOUT, max_retries=API_MAX_RETRIES)
        return self._client

    async def authenticate(self, api_key: str = None) -> bool:
        """
        Authenticate with xAI using an API key.

        Args:
            api_key: xAI API key (if not provided, uses stored key)

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
                self.status = ProviderStatus.ERROR
                return False

            # Create client and validate
            self._client = OpenAI(api_key=self._api_key, base_url=self.BASE_URL, timeout=API_TIMEOUT, max_retries=API_MAX_RETRIES)

            # Test the API key with a simple request
            try:
                self._client.models.list()
            except Exception as e:
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
            self.status = ProviderStatus.ERROR
            return False

    async def transcribe(
        self,
        audio_data: bytes,
        prompt: Optional[str] = None,
        language: str = "en",
    ) -> TranscriptionResult:
        """
        Transcribe audio using Grok.

        Note: xAI may not support audio transcription directly.
        If not supported, this will return an error suggesting to use another provider.

        Args:
            audio_data: Audio bytes (WAV format)
            prompt: Optional transcription prompt
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
                    error="Not authenticated. Please connect Grok first.",
                )

            # Try audio transcription if available
            # xAI API may support this in the future
            try:
                audio_file = io.BytesIO(audio_data)
                audio_file.name = "audio.wav"

                transcription = client.audio.transcriptions.create(
                    model="whisper-1",  # May need to be updated for xAI's model
                    file=audio_file,
                    response_format="text",
                )

                duration_ms = int((time.time() - start_time) * 1000)
                text = transcription if isinstance(transcription, str) else transcription.text

                return TranscriptionResult(
                    text=text.strip(),
                    raw_text=text,
                    duration_ms=duration_ms,
                )

            except Exception as audio_error:
                # Audio transcription not supported, return helpful error
                return TranscriptionResult(
                    text="",
                    error="Grok does not support audio transcription. Please use Groq or ChatGPT for transcription.",
                )

        except Exception as e:
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
        Transform text using Grok.

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
                    error="Not authenticated. Please connect Grok first.",
                )

            # Build the prompt
            system_prompt = "You are a text transformation assistant. Transform the given text according to the user's command. Return ONLY the transformed text, nothing else."

            user_prompt = f"Command: {command}\n\nText to transform:\n{text}"
            if context:
                user_prompt += f"\n\nContext: {context}"

            # Call Grok API
            response = client.chat.completions.create(
                model=self.CHAT_MODEL,
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
            return TransformResult(
                text="",
                original_text=text,
                command=command,
                error=str(e),
            )

    def is_authenticated(self) -> bool:
        """
        Check if xAI API key exists.

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
            self._client = OpenAI(api_key=stored_key, base_url=self.BASE_URL, timeout=API_TIMEOUT, max_retries=API_MAX_RETRIES)
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

        except Exception:
            return False

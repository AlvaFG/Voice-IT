"""
Voice IT - Gemini Provider
Uses Google's Gemini API for speech-to-text transcription and text transformation.
"""

import base64
import time
from typing import Optional

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from voice_it.providers.base_provider import (
    BaseProvider,
    ProviderStatus,
    TranscriptionResult,
    TransformResult,
)
from voice_it.storage.auth_store import AuthStore
from voice_it.storage.config import Config


class GeminiAdapter(BaseProvider):
    """
    Gemini provider using Google's Generative AI API.

    Uses Gemini 1.5 Flash for both audio transcription and text transformation.
    """

    PROVIDER_NAME = "gemini"
    DISPLAY_NAME = "Gemini"

    # Gemini model (supports audio natively)
    MODEL_NAME = "gemini-1.5-flash"

    def __init__(self, auth_store: AuthStore, config: Config):
        """
        Initialize the Gemini provider.

        Args:
            auth_store: Authentication store for API key
            config: Application configuration
        """
        if genai is None:
            raise ImportError(
                "google-generativeai not installed. Run: pip install google-generativeai"
            )

        super().__init__(auth_store, config)
        self._model = None
        self._api_key: Optional[str] = None

        # Try to load existing API key
        self._load_api_key()

    def _load_api_key(self):
        """Load API key from storage."""
        api_key = self.auth_store.get_token(self.PROVIDER_NAME, "api_key")
        if api_key:
            self._api_key = api_key
            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel(self.MODEL_NAME)

    def _get_model(self):
        """Get or create Gemini model."""
        if self._model is None and self._api_key:
            genai.configure(api_key=self._api_key)
            self._model = genai.GenerativeModel(self.MODEL_NAME)
        return self._model

    async def authenticate(self, api_key: str = None) -> bool:
        """
        Authenticate with Google AI using an API key.

        Args:
            api_key: Google AI API key (if not provided, uses stored key)

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

            # Configure and validate
            genai.configure(api_key=self._api_key)

            # Test the API key with a simple request
            try:
                model = genai.GenerativeModel(self.MODEL_NAME)
                # Simple test to validate API key
                response = model.generate_content("Say 'ok'")
                if not response.text:
                    raise Exception("Invalid response")
                self._model = model
            except Exception:
                self._api_key = None
                self._model = None
                self.status = ProviderStatus.ERROR
                return False

            # Save the API key
            if api_key:  # Only save if a new key was provided
                self.auth_store.save_token(self.PROVIDER_NAME, "api_key", api_key)

            # Update config
            self.config.set(f"provider.connected.{self.PROVIDER_NAME}", True)

            self.status = ProviderStatus.CONNECTED
            return True

        except Exception:
            self.status = ProviderStatus.ERROR
            return False

    async def transcribe(
        self,
        audio_data: bytes,
        prompt: Optional[str] = None,
        language: str = "en",
    ) -> TranscriptionResult:
        """
        Transcribe audio using Gemini.

        Gemini 1.5 Flash supports audio natively.

        Args:
            audio_data: Audio bytes (WAV format)
            prompt: Optional transcription prompt
            language: Language code (default: "en")

        Returns:
            TranscriptionResult with transcribed text or error
        """
        start_time = time.time()

        try:
            model = self._get_model()
            if not model:
                return TranscriptionResult(
                    text="",
                    error="Not authenticated. Please connect Gemini first.",
                )

            # Default transcription prompt
            if prompt is None:
                prompt = "Please transcribe this audio recording accurately. Return ONLY the transcribed text, nothing else."

            # Create audio part for Gemini
            audio_part = {
                "mime_type": "audio/wav",
                "data": base64.b64encode(audio_data).decode("utf-8")
            }

            # Generate transcription
            response = model.generate_content([audio_part, prompt])

            if not response.text:
                return TranscriptionResult(
                    text="",
                    error="Empty response from Gemini",
                )

            duration_ms = int((time.time() - start_time) * 1000)

            return TranscriptionResult(
                text=response.text.strip(),
                raw_text=response.text,
                duration_ms=duration_ms,
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
        Transform text using Gemini.

        Args:
            text: Text to transform
            command: Transformation command (e.g., "make formal", "fix grammar")
            context: Optional context for the transformation

        Returns:
            TransformResult with transformed text or error
        """
        try:
            model = self._get_model()
            if not model:
                return TransformResult(
                    text="",
                    original_text=text,
                    command=command,
                    error="Not authenticated. Please connect Gemini first.",
                )

            # Build the prompt
            prompt = f"""Transform the following text according to this command: {command}

Text to transform:
{text}
"""
            if context:
                prompt += f"\nContext: {context}"

            prompt += "\n\nReturn ONLY the transformed text, nothing else."

            # Generate transformation
            response = model.generate_content(prompt)

            if not response.text:
                return TransformResult(
                    text="",
                    original_text=text,
                    command=command,
                    error="Empty response from Gemini",
                )

            return TransformResult(
                text=response.text.strip(),
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
        Check if Google AI API key exists.

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
            genai.configure(api_key=stored_key)
            self._model = genai.GenerativeModel(self.MODEL_NAME)
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
            model = self._get_model()
            if not model:
                return False

            # Test with a simple request
            response = model.generate_content("Say 'ok'")
            return bool(response.text)

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
            self._model = None

            # Clear stored key
            self.auth_store.delete_token(self.PROVIDER_NAME, "api_key")

            # Update config
            self.config.set(f"provider.connected.{self.PROVIDER_NAME}", False)

            self.status = ProviderStatus.DISCONNECTED
            return True

        except Exception:
            return False

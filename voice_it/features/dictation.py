"""
Voice IT - Dictation Feature
Handles the complete dictation flow: record -> transcribe -> paste.
"""

import asyncio
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from voice_it.core.audio_engine import AudioEngine
from voice_it.core.paste_handler import PasteHandler, get_paste_handler
from voice_it.core.context_detector import ContextDetector, AppContext, get_context_detector
from voice_it.providers import (
    ProviderManager,
    TranscriptionResult,
    get_provider_manager,
    run_async,
)
from voice_it.storage.config import Config, get_config
from voice_it.storage.database import Database, get_database


class DictationState(Enum):
    """States of the dictation flow."""
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class DictationEvent:
    """Event data for dictation state changes."""
    state: DictationState
    text: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class DictationHandler:
    """
    Manages the complete dictation flow.
    Coordinates audio recording, AI transcription, and text pasting.
    """

    def __init__(
        self,
        audio_engine: Optional[AudioEngine] = None,
        provider_manager: Optional[ProviderManager] = None,
        paste_handler: Optional[PasteHandler] = None,
        config: Optional[Config] = None,
        database: Optional[Database] = None,
        context_detector: Optional[ContextDetector] = None,
    ):
        """
        Initialize the dictation handler.

        Args:
            audio_engine: Audio recorder (creates new if not provided)
            provider_manager: AI provider manager (uses global if not provided)
            paste_handler: Clipboard handler (uses global if not provided)
            config: App configuration (uses global if not provided)
            database: History database (uses global if not provided)
            context_detector: Context detector (uses global if not provided)
        """
        self.config = config or get_config()
        self.database = database or get_database()
        self.provider_manager = provider_manager or get_provider_manager()
        self.paste_handler = paste_handler or get_paste_handler()
        self.context_detector = context_detector or get_context_detector()

        # Audio engine - create if not provided
        if audio_engine is None:
            self.audio_engine = AudioEngine(
                sample_rate=self.config.get("audio.sample_rate", 16000),
                channels=self.config.get("audio.channels", 1),
            )
            self._owns_audio_engine = True
        else:
            self.audio_engine = audio_engine
            self._owns_audio_engine = False

        # State
        self._state = DictationState.IDLE
        self._lock = threading.Lock()
        self._processing_thread: Optional[threading.Thread] = None
        self._current_context: Optional[AppContext] = None

        # Callbacks
        self._state_callback: Optional[Callable[[DictationEvent], None]] = None
        self._audio_level_callback: Optional[Callable[[float], None]] = None

    @property
    def state(self) -> DictationState:
        """Get current dictation state."""
        return self._state

    @state.setter
    def state(self, value: DictationState):
        """Set dictation state."""
        self._state = value

    def set_state_callback(self, callback: Callable[[DictationEvent], None]):
        """Set callback for state changes."""
        self._state_callback = callback

    def set_audio_level_callback(self, callback: Callable[[float], None]):
        """Set callback for audio level updates during recording."""
        self._audio_level_callback = callback

    def _notify_state(
        self,
        state: DictationState,
        text: Optional[str] = None,
        error: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ):
        """Notify callback of state change."""
        self._state = state
        if self._state_callback:
            event = DictationEvent(
                state=state,
                text=text,
                error=error,
                duration_ms=duration_ms,
            )
            self._state_callback(event)

    def start_recording(self) -> bool:
        """
        Start recording audio.

        Returns:
            True if recording started, False if already recording/processing
        """
        with self._lock:
            if self._state != DictationState.IDLE:
                return False

            # Capture context BEFORE recording starts (while user is in target app)
            try:
                self._current_context = self.context_detector.get_active_app()
            except Exception:
                self._current_context = None

            # Check if any provider is connected
            if not self.provider_manager.is_any_connected():
                self._notify_state(
                    DictationState.ERROR,
                    error="No AI provider connected. Please connect a provider first.",
                )
                return False

            try:
                self.audio_engine.start_recording(
                    on_audio_level=self._audio_level_callback
                )
                self._notify_state(DictationState.RECORDING)
                return True
            except Exception as e:
                self._notify_state(DictationState.ERROR, error=str(e))
                return False

    def stop_recording(self) -> bool:
        """
        Stop recording and start processing.

        Returns:
            True if stopped successfully, False if not recording
        """
        with self._lock:
            if self._state != DictationState.RECORDING:
                return False

            try:
                # Stop recording and get audio data
                audio_data = self.audio_engine.stop_recording()

                if audio_data is None or len(audio_data) == 0:
                    self._notify_state(
                        DictationState.ERROR,
                        error="No audio recorded",
                    )
                    return False

                # Update state to processing
                self._notify_state(DictationState.PROCESSING)

                # Process in background thread (pass context)
                self._processing_thread = threading.Thread(
                    target=self._process_audio,
                    args=(audio_data, self._current_context),
                    daemon=True,
                )
                self._processing_thread.start()
                return True

            except Exception as e:
                self._notify_state(DictationState.ERROR, error=str(e))
                return False

    def _process_audio(self, audio_data: bytes, context: Optional[AppContext] = None):
        """
        Process recorded audio in background thread.

        Args:
            audio_data: WAV audio bytes
            context: Optional app context for transcription hints
        """
        try:
            # Build context hint for transcription
            app_name = None
            if context:
                app_name = context.app_name

            # Get transcription from AI
            result = run_async(
                self.provider_manager.transcribe(
                    audio_data=audio_data,
                    language=self.config.get("general.language", "en"),
                )
            )

            if result.success:
                final_text = result.text

                # Auto-polish: clean up filler words, fix grammar using dictation prompt
                if self.config.get("dictation.auto_polish", True):
                    try:
                        prompt = self._build_dictation_prompt()
                        polish_result = run_async(
                            self.provider_manager.transform(
                                text=final_text,
                                command=prompt,
                            )
                        )
                        if polish_result.success and polish_result.text:
                            final_text = polish_result.text
                    except Exception as e:
                        # If polish fails, use original text
                        print(f"Auto-polish failed, using original: {e}")

                # Paste the transcribed text
                paste_success = self.paste_handler.paste_text(final_text)

                if not paste_success:
                    # Fallback: just copy to clipboard
                    self.paste_handler.copy_to_clipboard(final_text)

                # Save to history (save original transcription, not expanded)
                try:
                    self.database.add_history(
                        text=final_text,
                        raw_text=result.text,  # Store original transcription
                        mode="dictation",
                        app_name=app_name,  # Store context app name
                        provider=self.provider_manager.active_provider_name,
                    )
                except Exception as e:
                    print(f"Error saving to history: {e}")

                # Notify success
                self._notify_state(
                    DictationState.SUCCESS,
                    text=final_text,
                    duration_ms=result.duration_ms,
                )
            else:
                # Transcription failed
                self._notify_state(
                    DictationState.ERROR,
                    error=result.error or "Transcription failed",
                )

        except Exception as e:
            self._notify_state(DictationState.ERROR, error=str(e))

        # Reset to idle after a delay
        time.sleep(2)
        self._notify_state(DictationState.IDLE)

    def _build_dictation_prompt(self) -> str:
        """
        Build the dictation prompt from template with config values.

        Returns:
            Formatted prompt string
        """
        from pathlib import Path

        # Load prompt template
        prompt_file = Path(__file__).parent.parent / "prompts" / "dictation.md"
        if not prompt_file.exists():
            return "Clean up this transcription: remove filler words, fix grammar and punctuation. Return only the cleaned text."

        prompt = prompt_file.read_text(encoding="utf-8")

        # Fill in placeholders
        language = self.config.get("general.language", "auto")
        if language == "auto":
            lang_config = "Detect the language automatically and transcribe in that language."
        else:
            lang_config = f"Transcribe in {language}."

        filler_words = self.config.get(
            "dictation.filler_words",
            "Remove: um, uh, er, ah, like, you know, I mean, sort of, kind of, basically"
        )

        number_format = self.config.get(
            "dictation.number_format",
            "Write numbers as digits for values > 10, words for 1-10"
        )

        custom_dict = self.config.get("dictation.custom_dictionary", "")
        if custom_dict:
            dict_text = f"Use these custom terms when applicable: {custom_dict}"
        else:
            dict_text = "No custom dictionary configured."

        # Replace placeholders
        prompt = prompt.replace("{{LANGUAGE_CONFIG}}", lang_config)
        prompt = prompt.replace("{{FILLER_WORDS}}", filler_words)
        prompt = prompt.replace("{{NUMBER_FORMAT}}", number_format)
        prompt = prompt.replace("{{CUSTOM_DICTIONARY}}", dict_text)

        return prompt

    def cancel(self):
        """Cancel current recording or processing."""
        with self._lock:
            if self._state == DictationState.RECORDING:
                self.audio_engine.stop_recording()
            self._notify_state(DictationState.IDLE)

    def cleanup(self):
        """Cleanup resources."""
        if self._owns_audio_engine:
            self.audio_engine.cleanup()


# Global dictation handler instance
_dictation_handler: Optional[DictationHandler] = None


def get_dictation_handler() -> DictationHandler:
    """Get the global dictation handler instance."""
    global _dictation_handler
    if _dictation_handler is None:
        _dictation_handler = DictationHandler()
    return _dictation_handler

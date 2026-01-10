"""
Voice IT - Main Application
Orchestrates all components: UI, audio, hotkeys, and AI providers.
"""

import sys
import threading
from typing import Optional

from voice_it import __app_name__, __version__
from voice_it.storage.config import get_config
from voice_it.core.hotkey_manager import HotkeyManager
from voice_it.core.audio_engine import AudioEngine
from voice_it.core.paste_handler import get_paste_handler
from voice_it.ui.tray import SystemTray
from voice_it.ui.window_manager import WindowManager
from voice_it.ui.recording_indicator import RecordingIndicator
from voice_it.features.dictation import (
    DictationHandler,
    DictationEvent,
    DictationState,
)
from voice_it.providers import get_provider_manager, run_async


class VoiceITApp:
    """
    Main application class for Voice IT.
    Manages the lifecycle of all components.
    """

    def __init__(self):
        """Initialize the Voice IT application."""
        self.config = get_config()

        # Component references
        self.hotkey_manager: Optional[HotkeyManager] = None
        self.audio_engine: Optional[AudioEngine] = None
        self.system_tray: Optional[SystemTray] = None
        self.window_manager: Optional[WindowManager] = None
        self.dictation_handler: Optional[DictationHandler] = None
        self.recording_indicator: Optional[RecordingIndicator] = None
        self.provider_manager = get_provider_manager()

        # State
        self.is_recording = False
        self.is_processing = False
        self._running = False

    def _initialize_components(self):
        """Initialize all application components."""
        print("Initializing components...")

        # Audio engine
        self.audio_engine = AudioEngine(
            sample_rate=self.config.get("audio.sample_rate", 16000),
            channels=self.config.get("audio.channels", 1),
        )

        # Dictation handler (uses audio engine and provider manager)
        self.dictation_handler = DictationHandler(
            audio_engine=self.audio_engine,
            provider_manager=self.provider_manager,
            paste_handler=get_paste_handler(),
            config=self.config,
        )
        self.dictation_handler.set_state_callback(self._on_dictation_state_change)

        # Hotkey manager
        self.hotkey_manager = HotkeyManager(
            on_record_start=self._on_record_start,
            on_record_stop=self._on_record_stop,
        )

        # System tray
        self.system_tray = SystemTray(
            on_open=self._show_window,
            on_settings=self._show_settings,
            on_exit=self._quit,
        )

        # Recording indicator (small corner popup)
        self.recording_indicator = RecordingIndicator()

        # Window manager (PyWebView-based main window)
        self.window_manager = WindowManager(
            on_close=self._hide_window,
            on_minimize=self._hide_window,
            on_quit=self._quit,
            on_provider_change=self._on_provider_change,
        )

        # Set audio level callback for indicator
        self.dictation_handler.set_audio_level_callback(self._on_audio_level)

        print("Components initialized.")

    def _on_dictation_state_change(self, event: DictationEvent):
        """Handle dictation state changes."""
        state = event.state

        # Map dictation state to tray icon state
        tray_state_map = {
            DictationState.IDLE: "idle",
            DictationState.RECORDING: "recording",
            DictationState.PROCESSING: "processing",
            DictationState.SUCCESS: "success",
            DictationState.ERROR: "error",
        }

        # Update tray icon
        if self.system_tray:
            self.system_tray.set_state(tray_state_map.get(state, "idle"))

        # Update window state
        if self.window_manager:
            if state == DictationState.RECORDING:
                self.window_manager.set_recording(True)
                self.window_manager.set_processing(False)
            elif state == DictationState.PROCESSING:
                self.window_manager.set_recording(False)
                self.window_manager.set_processing(True)
            else:
                self.window_manager.set_recording(False)
                self.window_manager.set_processing(False)

        # Log events
        if state == DictationState.SUCCESS:
            print(f"[Transcription] {event.text}")
            if self.window_manager:
                self.window_manager.notify_transcription(event.text, True)
        elif state == DictationState.ERROR:
            print(f"[Error] {event.error}")
            if self.window_manager:
                self.window_manager.notify_error(event.error)

        # Update internal state flags
        self.is_recording = (state == DictationState.RECORDING)
        self.is_processing = (state == DictationState.PROCESSING)

        # Show/hide recording indicator
        # TEMPORARILY DISABLED - PyWebView threading issue
        # The RecordingIndicator.show() creates a window from a secondary thread
        # which violates PyWebView's threading model and blocks the flow
        # if self.recording_indicator:
        #     if state == DictationState.RECORDING:
        #         self.recording_indicator.show()
        #     elif state in (DictationState.PROCESSING, DictationState.SUCCESS,
        #                   DictationState.ERROR, DictationState.IDLE):
        #         self.recording_indicator.hide()

    def _on_audio_level(self, level: float):
        """Handle audio level updates during recording."""
        if self.recording_indicator and self.recording_indicator.is_visible:
            self.recording_indicator.update_audio_level(level)

    def _on_record_start(self):
        """Called when recording starts (hotkey pressed)."""
        if self.is_recording or self.is_processing:
            return

        print("[Recording started]")

        if self.dictation_handler:
            self.dictation_handler.start_recording()

    def _on_record_stop(self):
        """Called when recording stops (hotkey released)."""
        if not self.is_recording:
            return

        print("[Recording stopped]")

        if self.dictation_handler:
            self.dictation_handler.stop_recording()

    def _on_provider_change(self, provider_id: str, connected: bool):
        """Handle provider connection status change."""
        print(f"[Provider] {provider_id}: {'connected' if connected else 'disconnected'}")

    def _show_window(self):
        """Show the main application window."""
        if self.window_manager:
            self.window_manager.show()

    def _hide_window(self):
        """Hide the main window (minimize to tray)."""
        if self.window_manager:
            self.window_manager.hide()

    def _show_settings(self):
        """Show the settings view."""
        if self.window_manager:
            self.window_manager.show()
            self.window_manager.navigate_to("settings")

    def _quit(self):
        """Quit the application."""
        print("Quitting Voice IT...")
        self._running = False

        # Cleanup components
        if self.hotkey_manager:
            self.hotkey_manager.stop()
        if self.dictation_handler:
            self.dictation_handler.cleanup()
        if self.recording_indicator:
            self.recording_indicator.destroy()
        if self.system_tray:
            self.system_tray.stop()
        if self.window_manager:
            self.window_manager.destroy()

        sys.exit(0)

    def connect_provider(self, provider_name: str) -> bool:
        """
        Connect to an AI provider.

        Args:
            provider_name: Name of provider ("claude", "chatgpt", "gemini")

        Returns:
            True if connection successful
        """
        try:
            return run_async(self.provider_manager.authenticate(provider_name))
        except Exception as e:
            print(f"Error connecting to {provider_name}: {e}")
            return False

    def disconnect_provider(self, provider_name: str) -> bool:
        """
        Disconnect from an AI provider.

        Args:
            provider_name: Name of provider

        Returns:
            True if disconnection successful
        """
        try:
            return run_async(self.provider_manager.disconnect(provider_name))
        except Exception as e:
            print(f"Error disconnecting from {provider_name}: {e}")
            return False

    def run(self):
        """Run the Voice IT application."""
        print(f"Starting {__app_name__} v{__version__}...")

        try:
            # Initialize components
            self._initialize_components()

            # Start hotkey listener in background thread
            if self.hotkey_manager:
                hotkey_thread = threading.Thread(
                    target=self.hotkey_manager.start,
                    daemon=True
                )
                hotkey_thread.start()

            # Start system tray in background thread
            if self.system_tray:
                tray_thread = threading.Thread(
                    target=self.system_tray.start,
                    daemon=True
                )
                tray_thread.start()

            self._running = True

            # Check provider connection status
            connected = self.provider_manager.get_connected_providers()
            if connected:
                print(f"Connected providers: {', '.join(connected)}")
            else:
                print("No providers connected. Go to Settings to connect a provider.")

            # Run main window (blocking - runs the PyWebView event loop)
            if self.window_manager:
                self.window_manager.run()

        except Exception as e:
            print(f"Error running application: {e}")
            self._quit()

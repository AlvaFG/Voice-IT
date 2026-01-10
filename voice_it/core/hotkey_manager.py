"""
Voice IT - Hotkey Manager
Handles global keyboard shortcuts for recording activation.
"""

import platform
import threading
from typing import Callable, Optional, Set

try:
    from pynput import keyboard
except ImportError:
    keyboard = None


class HotkeyManager:
    """
    Global hotkey manager for Voice IT.
    Listens for hotkey combinations to start/stop recording.

    Default hotkey:
    - Dictation: Ctrl + Win/Cmd (hold to record)
    """

    def __init__(
        self,
        on_record_start: Optional[Callable[[], None]] = None,
        on_record_stop: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize the hotkey manager.

        Args:
            on_record_start: Callback when dictation recording should start
            on_record_stop: Callback when dictation recording should stop
        """
        if keyboard is None:
            raise ImportError(
                "pynput not installed. Run: pip install pynput"
            )

        self.on_record_start = on_record_start
        self.on_record_stop = on_record_stop

        # Determine platform-specific modifier key
        self._system = platform.system()
        self._modifier_key = self._get_modifier_key()

        # State tracking
        self._pressed_keys: Set = set()
        self._is_recording = False
        self._listener: Optional[keyboard.Listener] = None
        self._running = False

        # Debounce tracking to prevent multiple triggers
        self._last_record_start_time = 0
        self._last_record_stop_time = 0
        self._debounce_interval = 0.5  # 500ms debounce

    def _get_modifier_key(self):
        """Get the platform-specific modifier key."""
        if self._system == "Darwin":  # macOS
            return keyboard.Key.cmd
        elif self._system == "Windows":
            return keyboard.Key.cmd  # Windows key
        else:  # Linux
            return keyboard.Key.cmd  # Super key

    def _check_dictation_hotkey(self) -> bool:
        """Check if the dictation hotkey combination is pressed (Ctrl + Win)."""
        ctrl_pressed = (
            keyboard.Key.ctrl_l in self._pressed_keys or
            keyboard.Key.ctrl_r in self._pressed_keys
        )
        modifier_pressed = self._modifier_key in self._pressed_keys

        # Dictation: Ctrl + Win
        return ctrl_pressed and modifier_pressed

    def _on_press(self, key):
        """Handle key press events."""
        import time

        self._pressed_keys.add(key)

        current_time = time.time()

        # Check dictation hotkey
        if self._check_dictation_hotkey() and not self._is_recording:
            # Debounce check
            if current_time - self._last_record_start_time < self._debounce_interval:
                print("[HOTKEY] Debounce: Ignoring duplicate start trigger")
                return

            print("[HOTKEY] Dictation hotkey detected! Calling on_record_start...")
            self._is_recording = True
            self._last_record_start_time = current_time
            if self.on_record_start:
                self.on_record_start()
                print("[HOTKEY] on_record_start callback finished")

    def _on_release(self, key):
        """Handle key release events."""
        import time

        # Remove key from pressed set
        self._pressed_keys.discard(key)

        current_time = time.time()

        # Check if dictation hotkey was released
        if self._is_recording and not self._check_dictation_hotkey():
            # Debounce check
            if current_time - self._last_record_stop_time < self._debounce_interval:
                print("[HOTKEY] Debounce: Ignoring duplicate stop trigger")
                return

            self._is_recording = False
            self._last_record_stop_time = current_time
            if self.on_record_stop:
                self.on_record_stop()

    def start(self):
        """Start listening for hotkeys."""
        if self._running:
            return

        self._running = True
        self._pressed_keys = set()

        mod_name = 'Cmd' if self._system == 'Darwin' else 'Win/Super'
        print(f"Hotkey listener starting...")
        print(f"Platform: {self._system}")
        print(f"Dictation hotkey: Ctrl + {mod_name}")

        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()

    def stop(self):
        """Stop listening for hotkeys."""
        self._running = False

        if self._listener:
            self._listener.stop()
            self._listener = None

        self._pressed_keys = set()
        print("Hotkey listener stopped.")

    @property
    def is_recording(self) -> bool:
        """Check if currently in dictation recording state."""
        return self._is_recording

    def set_hotkey(self, keys: list):
        """
        Set custom hotkey combination.

        Args:
            keys: List of key names (e.g., ["ctrl", "win"])
        """
        # TODO: Implement custom hotkey configuration
        pass

"""
Voice IT - Hotkey Manager
Handles global keyboard shortcuts for recording activation.
"""

import ctypes
import logging
import platform
import threading
import time
from typing import Callable, Optional, Set

try:
    from pynput import keyboard
except ImportError:
    keyboard = None

logger = logging.getLogger(__name__)

# Windows virtual-key codes (used for real-time physical key state checks)
_VK_CONTROL = 0x11
_VK_LWIN = 0x5B
_VK_RWIN = 0x5C
_KEY_DOWN_MASK = 0x8000


class HotkeyManager:
    """
    Global hotkey manager for Voice IT.
    Listens for hotkey combinations to start/stop recording.

    Default hotkey:
    - Dictation: Ctrl + Win/Cmd (hold to record)

    On Windows the combo is confirmed by reading the real-time physical key
    state (GetAsyncKeyState) instead of trusting an accumulated key set. This
    avoids the classic "stuck modifier" bug: the Win-key release event is often
    swallowed by the OS, which would leave Win marked as pressed and cause a
    false trigger when only Ctrl is later pressed. While recording, a small
    watchdog polls the physical state so recording always stops when the combo
    is released, even if pynput drops the release event entirely.

    On macOS/Linux there is no equivalent physical-state probe here, so those
    platforms fall back to a normalized pressed-key set (best effort): a
    swallowed modifier-release event can still leave a stale modifier.
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

        # Platform
        self._system = platform.system()
        self._is_windows = self._system == "Windows"

        # State tracking (guarded by _lock; mutated from the listener thread)
        self._lock = threading.Lock()
        self._pressed_keys: Set = set()
        self._is_recording = False
        self._listener: Optional["keyboard.Listener"] = None
        self._running = False

        # Debounce tracking to prevent multiple triggers
        self._last_record_start_time = 0.0
        self._last_record_stop_time = 0.0
        self._debounce_interval = 0.5  # 500ms debounce

    @staticmethod
    def _normalize(key):
        """
        Collapse left/right modifier variants to a single canonical key so that
        press/release events match symmetrically (e.g. right Win = cmd_r is
        treated the same as left Win = cmd).
        """
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r, keyboard.Key.ctrl):
            return keyboard.Key.ctrl
        if key in (keyboard.Key.cmd_l, keyboard.Key.cmd_r, keyboard.Key.cmd):
            return keyboard.Key.cmd
        return key

    def _combo_physically_held(self) -> bool:
        """
        Windows only: return True only if Ctrl AND a Win key are physically held
        right now, read straight from the hardware state. Immune to missed/stuck
        key events.
        """
        try:
            user32 = ctypes.windll.user32

            def down(vk: int) -> bool:
                return bool(user32.GetAsyncKeyState(vk) & _KEY_DOWN_MASK)

            ctrl_down = down(_VK_CONTROL)
            win_down = down(_VK_LWIN) or down(_VK_RWIN)
            return ctrl_down and win_down
        except Exception:
            return False

    def _check_dictation_hotkey(self) -> bool:
        """Check if the dictation hotkey combination is pressed (Ctrl + Win)."""
        if self._is_windows:
            # Trust the real keyboard state, not the accumulated set.
            return self._combo_physically_held()

        # macOS / Linux: rely on the normalized pressed-key set.
        return (
            keyboard.Key.ctrl in self._pressed_keys
            and keyboard.Key.cmd in self._pressed_keys
        )

    def _on_press(self, key):
        """Handle key press events."""
        should_start = False
        with self._lock:
            self._pressed_keys.add(self._normalize(key))

            if self._check_dictation_hotkey() and not self._is_recording:
                now = time.monotonic()
                if now - self._last_record_start_time >= self._debounce_interval:
                    self._is_recording = True
                    self._last_record_start_time = now
                    should_start = True

        if should_start:
            logger.debug("Dictation hotkey detected -> start recording")
            if self._is_windows:
                # On Windows the watchdog owns stop detection (see below).
                self._start_release_watchdog()
            if self.on_record_start:
                self.on_record_start()

    def _on_release(self, key):
        """Handle key release events."""
        # Keep the pressed-key set current on every platform.
        with self._lock:
            self._pressed_keys.discard(self._normalize(key))

        # On Windows, stop is driven by the watchdog polling physical state, so
        # it is immune to dropped/debounced release events. Nothing to do here.
        if self._is_windows:
            return

        # macOS/Linux: stop as soon as the combo is no longer held.
        should_stop = False
        with self._lock:
            if self._is_recording and not self._check_dictation_hotkey():
                now = time.monotonic()
                if now - self._last_record_stop_time >= self._debounce_interval:
                    self._is_recording = False
                    self._last_record_stop_time = now
                    should_stop = True

        if should_stop:
            logger.debug("Dictation hotkey released -> stop recording")
            if self.on_record_stop:
                self.on_record_stop()

    def _start_release_watchdog(self):
        """
        Windows: while recording, poll the physical key state and stop as soon
        as Ctrl+Win is no longer held. This makes stop detection independent of
        pynput release events (which the OS can swallow or the debounce drop),
        so recording can never get stuck on.
        """
        def watch():
            while True:
                time.sleep(0.05)

                should_stop = False
                with self._lock:
                    if not self._is_recording:
                        return  # already stopped elsewhere
                    if not self._combo_physically_held():
                        self._is_recording = False
                        self._last_record_stop_time = time.monotonic()
                        should_stop = True

                if should_stop:
                    logger.debug("Dictation combo released (watchdog) -> stop recording")
                    if self.on_record_stop:
                        self.on_record_stop()
                    return

        threading.Thread(target=watch, daemon=True).start()

    def start(self):
        """Start listening for hotkeys."""
        if self._running:
            return

        self._running = True
        with self._lock:
            self._pressed_keys = set()

        mod_name = "Cmd" if self._system == "Darwin" else "Win/Super"
        logger.info(
            "Hotkey listener starting (platform=%s, dictation=Ctrl + %s)",
            self._system,
            mod_name,
        )

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

        with self._lock:
            self._pressed_keys = set()
        logger.info("Hotkey listener stopped.")

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
        # TODO: Implement custom hotkey configuration. The dictation combo is
        # currently fixed to Ctrl + Win (matches the default config).
        pass

"""
Voice IT - Recording Indicator
Small floating window for recording feedback.
"""

import platform
import threading
import time
from pathlib import Path
from typing import Optional

import webview


def get_web_path(filename: str) -> str:
    """Get absolute path to a web asset file."""
    base = Path(__file__).parent / "web"
    return str(base / filename)


class RecordingIndicator:
    """
    Small floating window that shows recording status.
    Positioned in the bottom-right corner of the screen.
    """

    WIDTH = 200
    HEIGHT = 60
    MARGIN = 20  # Distance from screen edge

    def __init__(self):
        """Initialize the recording indicator."""
        self._window: Optional[webview.Window] = None
        self._is_visible = False
        self._start_time: float = 0
        self._timer_thread: Optional[threading.Thread] = None
        self._timer_running = False

    def _get_position(self) -> tuple:
        """Calculate bottom-right position for the indicator."""
        # Get screen size - this varies by platform
        try:
            if platform.system() == "Windows":
                import ctypes
                user32 = ctypes.windll.user32
                screen_width = user32.GetSystemMetrics(0)
                screen_height = user32.GetSystemMetrics(1)
            else:
                # Default fallback
                screen_width = 1920
                screen_height = 1080
        except Exception:
            screen_width = 1920
            screen_height = 1080

        x = screen_width - self.WIDTH - self.MARGIN
        y = screen_height - self.HEIGHT - self.MARGIN - 50  # Extra margin for taskbar

        return x, y

    def _timer_loop(self):
        """Background thread that updates the timer display."""
        while self._timer_running and self._is_visible:
            elapsed = time.time() - self._start_time
            self._update_time(elapsed)
            time.sleep(0.1)

    def _update_time(self, seconds: float):
        """Update the time display in the indicator."""
        if self._window and self._is_visible:
            try:
                self._window.evaluate_js(f"updateTime({seconds})")
            except Exception:
                pass  # Window may have been destroyed

    def _update_level(self, level: float):
        """Update the audio level display."""
        if self._window and self._is_visible:
            try:
                self._window.evaluate_js(f"updateLevel({level})")
            except Exception:
                pass

    def _on_loaded(self):
        """Called when the indicator page loads."""
        # Position the window
        x, y = self._get_position()
        if self._window:
            try:
                self._window.move(x, y)
            except Exception:
                pass

    def show(self):
        """Show the recording indicator."""
        if self._is_visible:
            return

        # Create window if needed
        if self._window is None:
            x, y = self._get_position()
            self._window = webview.create_window(
                title="",
                url=get_web_path("recording.html"),
                width=self.WIDTH,
                height=self.HEIGHT,
                x=x,
                y=y,
                resizable=False,
                frameless=True,
                on_top=True,
                transparent=True,
                easy_drag=False,
                background_color="#0D0D0D",
            )
            self._window.events.loaded += self._on_loaded
        else:
            self._window.show()

        self._is_visible = True
        self._start_time = time.time()

        # Start timer thread
        self._timer_running = True
        self._timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self._timer_thread.start()

    def hide(self):
        """Hide the recording indicator."""
        if not self._is_visible:
            return

        # Stop timer
        self._timer_running = False
        if self._timer_thread:
            self._timer_thread.join(timeout=0.5)
            self._timer_thread = None

        # Hide window
        if self._window:
            try:
                self._window.hide()
            except Exception:
                pass

        self._is_visible = False
        self._start_time = 0

    def update_audio_level(self, level: float):
        """
        Update the audio level meter.

        Args:
            level: Audio level from 0.0 to 1.0
        """
        if self._is_visible:
            self._update_level(max(0.0, min(1.0, level)))

    def destroy(self):
        """Destroy the indicator window."""
        self._timer_running = False
        if self._timer_thread:
            self._timer_thread.join(timeout=0.5)
        if self._window:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None
        self._is_visible = False

    @property
    def is_visible(self) -> bool:
        """Check if indicator is visible."""
        return self._is_visible

"""
Voice IT - Window Manager
Manages PyWebView windows for the application.
"""

import ctypes
import json
import os
import sys
import threading
from pathlib import Path
from typing import Callable, Dict, Optional

import webview

from voice_it import __app_name__


def get_web_path(filename: str) -> str:
    """Get absolute path to a web asset file."""
    base = Path(__file__).parent / "web"
    return str(base / filename)


def get_icon_path() -> str:
    """Get absolute path to the application icon."""
    icon_path = Path(__file__).parent / "assets" / "icon.ico"
    return str(icon_path) if icon_path.exists() else ""


def set_windows_app_id():
    """
    Set the AppUserModelID for Windows taskbar grouping.
    This ensures the app shows its own icon instead of Python's.
    """
    if sys.platform == "win32":
        try:
            app_id = "VoiceIT.VoiceIT.Desktop.1"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass  # Silently fail on non-Windows or permission issues


# Set AppUserModelID early, before window creation
set_windows_app_id()

# Import bridge after setting AppUserModelID
from voice_it.ui.bridge import VoiceITAPI


class WindowManager:
    """
    Manages the main application window using PyWebView.
    """

    WIDTH = 520
    HEIGHT = 720
    MIN_WIDTH = 440
    MIN_HEIGHT = 560

    def __init__(
        self,
        on_close: Optional[Callable] = None,
        on_minimize: Optional[Callable] = None,
        on_quit: Optional[Callable] = None,
        on_provider_change: Optional[Callable] = None,
    ):
        """
        Initialize the window manager.

        Args:
            on_close: Callback when window close requested (minimize to tray)
            on_minimize: Callback when minimize requested
            on_quit: Callback when quit requested
            on_provider_change: Callback when provider status changes
        """
        self._on_close = on_close
        self._window: Optional[webview.Window] = None
        self._api: Optional[VoiceITAPI] = None
        self._is_visible = False
        self._hwnd = None  # Windows handle for taskbar manipulation

        # Create API bridge with callbacks
        self._api = VoiceITAPI(
            callbacks={
                "on_minimize": on_minimize or self.hide,
                "on_quit": on_quit,
                "on_provider_change": on_provider_change,
            }
        )

    def _on_window_close(self):
        """Handle window close event - minimize to tray instead of closing."""
        if self._on_close:
            self._on_close()
        return False  # Prevent actual close

    def _on_loaded(self):
        """Called when the web page finishes loading."""
        self._is_visible = True
        if self._window and self._api:
            self._api.set_window(self._window)

    def create(self):
        """Create the main window."""
        self._window = webview.create_window(
            title=__app_name__,
            url=get_web_path("index.html"),
            width=self.WIDTH,
            height=self.HEIGHT,
            min_size=(self.MIN_WIDTH, self.MIN_HEIGHT),
            resizable=True,
            frameless=False,
            easy_drag=False,
            js_api=self._api,
            background_color="#0D0D0D",
        )

        # Set up event handlers
        self._window.events.loaded += self._on_loaded
        self._window.events.closing += self._on_window_close

    def run(self, start_hidden: bool = False):
        """
        Start the PyWebView event loop (blocking).

        Args:
            start_hidden: If True, start with window hidden (minimized to tray).
        """
        if self._window is None:
            self.create()

        # Set window icon on Windows before starting
        if sys.platform == "win32":
            icon_path = get_icon_path()
            if icon_path:
                self._schedule_icon_update(icon_path, start_hidden)

        # If starting hidden, hide window immediately after creation
        if start_hidden:
            self._schedule_hide()

        # Start webview - this blocks until all windows are closed
        webview.start(debug=False)

    def _schedule_hide(self):
        """Schedule hiding the window after it's created (for background mode)."""
        def hide_window():
            import time
            time.sleep(0.8)  # Wait for window to be created
            if self._window:
                self._window.hide()
                self._is_visible = False
            # Note: _hide_from_taskbar is called in _schedule_icon_update when start_hidden=True

        threading.Thread(target=hide_window, daemon=True).start()

    def _schedule_icon_update(self, icon_path: str, start_hidden: bool = False):
        """Schedule icon update after window is created."""
        import ctypes

        def set_icon():
            import time
            # Wait for window to be fully created
            time.sleep(1.5 if not start_hidden else 0.5)

            try:
                user32 = ctypes.windll.user32

                # Find window by title - retry a few times
                hwnd = None
                for _ in range(5):
                    hwnd = user32.FindWindowW(None, __app_name__)
                    if hwnd:
                        break
                    time.sleep(0.3)

                if not hwnd:
                    return

                # Store hwnd for later use
                self._hwnd = hwnd

                # Load icons at proper sizes
                IMAGE_ICON = 1
                LR_LOADFROMFILE = 0x0010

                # Load small icon (16x16 for titlebar)
                hicon_small = user32.LoadImageW(
                    None,
                    icon_path,
                    IMAGE_ICON,
                    16,
                    16,
                    LR_LOADFROMFILE
                )

                # Load big icon (32x32 for alt-tab, taskbar)
                hicon_big = user32.LoadImageW(
                    None,
                    icon_path,
                    IMAGE_ICON,
                    32,
                    32,
                    LR_LOADFROMFILE
                )

                # Load extra large icon (48x48 for taskbar on higher DPI)
                hicon_large = user32.LoadImageW(
                    None,
                    icon_path,
                    IMAGE_ICON,
                    48,
                    48,
                    LR_LOADFROMFILE
                )

                WM_SETICON = 0x0080
                ICON_SMALL = 0
                ICON_BIG = 1

                if hicon_small:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)

                if hicon_big:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
                elif hicon_large:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_large)

                # If starting hidden, hide from taskbar
                if start_hidden:
                    self._hide_from_taskbar(hwnd)

            except Exception as e:
                pass  # Icon is optional

        threading.Thread(target=set_icon, daemon=True).start()

    def _hide_from_taskbar(self, hwnd=None):
        """Hide the window from the taskbar (Windows only)."""
        if sys.platform != "win32":
            return

        import ctypes

        if hwnd is None:
            hwnd = getattr(self, '_hwnd', None)
            if not hwnd:
                user32 = ctypes.windll.user32
                hwnd = user32.FindWindowW(None, __app_name__)

        if not hwnd:
            return

        try:
            user32 = ctypes.windll.user32

            # Window style constants
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080  # Hide from taskbar
            WS_EX_APPWINDOW = 0x00040000   # Show in taskbar

            # Get current extended style
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)

            # Add TOOLWINDOW (hides from taskbar) and remove APPWINDOW
            new_style = (ex_style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)

        except Exception:
            pass

    def _show_in_taskbar(self, hwnd=None):
        """Show the window in the taskbar (Windows only)."""
        if sys.platform != "win32":
            return

        import ctypes

        if hwnd is None:
            hwnd = getattr(self, '_hwnd', None)
            if not hwnd:
                user32 = ctypes.windll.user32
                hwnd = user32.FindWindowW(None, __app_name__)

        if not hwnd:
            return

        try:
            user32 = ctypes.windll.user32

            # Window style constants
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_APPWINDOW = 0x00040000

            # Get current extended style
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)

            # Remove TOOLWINDOW and add APPWINDOW
            new_style = (ex_style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)

        except Exception:
            pass

    def show(self):
        """Show the window and add to taskbar."""
        if self._window:
            # First show in taskbar, then show window
            self._show_in_taskbar()
            self._window.show()
            self._is_visible = True

    def hide(self):
        """Hide the window (minimize to tray) and remove from taskbar."""
        if self._window:
            self._window.hide()
            self._hide_from_taskbar()
            self._is_visible = False

    def destroy(self):
        """Destroy the window."""
        if self._window:
            self._window.destroy()
            self._window = None
            self._is_visible = False

    @property
    def is_visible(self) -> bool:
        """Check if window is visible."""
        return self._is_visible

    # =========================================================================
    # STATE NOTIFICATIONS (Python -> JavaScript)
    # =========================================================================

    def notify_state_change(self, state: str, data: Optional[Dict] = None):
        """
        Push state change to JavaScript.

        Args:
            state: State name (recording, processing, idle, etc.)
            data: Optional data dict to send
        """
        if self._window:
            data_json = json.dumps(data) if data else "null"
            self._window.evaluate_js(f"App.onStateChange('{state}', {data_json})")

    def notify_recording_start(self):
        """Notify JS that recording started."""
        self.notify_state_change("recording", {"active": True})

    def notify_recording_stop(self):
        """Notify JS that recording stopped."""
        self.notify_state_change("recording", {"active": False})

    def notify_processing(self, active: bool = True):
        """Notify JS of processing state."""
        self.notify_state_change("processing", {"active": active})

    def notify_transcription(self, text: str, success: bool = True):
        """Notify JS of transcription result."""
        self.notify_state_change(
            "transcription",
            {"text": text, "success": success},
        )

    def notify_error(self, message: str):
        """Notify JS of an error."""
        self.notify_state_change("error", {"message": message})

    def navigate_to(self, view: str):
        """
        Navigate to a specific view.

        Args:
            view: View name (home, settings, history, snippets, dictionary)
        """
        if self._window:
            self._window.evaluate_js(f"App.navigateTo('{view}')")

    def set_recording(self, is_recording: bool):
        """Update recording state in UI."""
        if is_recording:
            self.notify_recording_start()
        else:
            self.notify_recording_stop()

    def set_processing(self, is_processing: bool):
        """Update processing state in UI."""
        self.notify_processing(is_processing)

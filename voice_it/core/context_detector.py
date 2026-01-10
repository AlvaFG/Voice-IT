"""
Voice IT - Context Detector
Detects the active application and provides context hints for transcription.
"""

import platform
from dataclasses import dataclass
from typing import Optional


@dataclass
class AppContext:
    """Context information about the active application."""
    app_name: str
    window_title: Optional[str] = None
    app_category: Optional[str] = None  # e.g., "code_editor", "email", "chat", "document"

    def get_context_hint(self) -> str:
        """Get a context hint string for AI prompts."""
        hints = []

        if self.app_category:
            category_hints = {
                "code_editor": "User is coding. Use technical language, proper syntax, variable names.",
                "email": "User is writing an email. Use professional, clear language.",
                "chat": "User is chatting. Use casual, conversational language.",
                "document": "User is writing a document. Use formal, structured language.",
                "browser": "User is browsing. Context varies.",
                "terminal": "User is in terminal. Use command-line appropriate language.",
                "notes": "User is taking notes. Use concise, bulleted format.",
            }
            if self.app_category in category_hints:
                hints.append(category_hints[self.app_category])

        if self.app_name:
            hints.append(f"Active app: {self.app_name}")

        return " ".join(hints) if hints else ""


class ContextDetector:
    """
    Detects the active application to provide context for transcription.

    Platform support:
    - Windows: Uses win32gui
    - macOS: Uses AppKit/NSWorkspace
    - Linux: Uses xdotool or wmctrl
    """

    # App name to category mapping
    APP_CATEGORIES = {
        # Code Editors
        "code": "code_editor",
        "visual studio": "code_editor",
        "vscode": "code_editor",
        "pycharm": "code_editor",
        "intellij": "code_editor",
        "sublime": "code_editor",
        "atom": "code_editor",
        "vim": "code_editor",
        "nvim": "code_editor",
        "neovim": "code_editor",
        "emacs": "code_editor",
        "cursor": "code_editor",

        # Email
        "outlook": "email",
        "mail": "email",
        "thunderbird": "email",
        "gmail": "email",
        "protonmail": "email",

        # Chat/Communication
        "slack": "chat",
        "discord": "chat",
        "teams": "chat",
        "telegram": "chat",
        "whatsapp": "chat",
        "signal": "chat",
        "zoom": "chat",
        "skype": "chat",
        "messenger": "chat",

        # Documents
        "word": "document",
        "docs": "document",
        "pages": "document",
        "libreoffice": "document",
        "writer": "document",
        "notion": "document",
        "obsidian": "notes",
        "evernote": "notes",
        "onenote": "notes",

        # Browsers
        "chrome": "browser",
        "firefox": "browser",
        "safari": "browser",
        "edge": "browser",
        "brave": "browser",
        "opera": "browser",
        "arc": "browser",

        # Terminal
        "terminal": "terminal",
        "iterm": "terminal",
        "cmd": "terminal",
        "powershell": "terminal",
        "warp": "terminal",
        "alacritty": "terminal",
        "kitty": "terminal",
        "hyper": "terminal",
        "windows terminal": "terminal",
    }

    def __init__(self):
        """Initialize the context detector."""
        self._system = platform.system()
        self._last_context: Optional[AppContext] = None

    def get_active_app(self) -> AppContext:
        """
        Get information about the currently active application.

        Returns:
            AppContext with app name, window title, and category
        """
        try:
            if self._system == "Windows":
                return self._get_windows_context()
            elif self._system == "Darwin":
                return self._get_macos_context()
            else:  # Linux
                return self._get_linux_context()
        except Exception as e:
            print(f"Error detecting context: {e}")
            return AppContext(app_name="Unknown")

    def _get_windows_context(self) -> AppContext:
        """Get context on Windows using win32gui."""
        try:
            import win32gui
            import win32process
            import psutil

            # Get foreground window handle
            hwnd = win32gui.GetForegroundWindow()
            window_title = win32gui.GetWindowText(hwnd)

            # Get process ID
            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            # Get process name
            try:
                process = psutil.Process(pid)
                app_name = process.name().replace(".exe", "")
            except:
                app_name = "Unknown"

            category = self._categorize_app(app_name, window_title)

            return AppContext(
                app_name=app_name,
                window_title=window_title,
                app_category=category,
            )

        except ImportError:
            return AppContext(app_name="Unknown")

    def _get_macos_context(self) -> AppContext:
        """Get context on macOS using AppKit."""
        try:
            from AppKit import NSWorkspace

            workspace = NSWorkspace.sharedWorkspace()
            active_app = workspace.activeApplication()

            app_name = active_app.get("NSApplicationName", "Unknown")

            # Try to get window title via accessibility (requires permissions)
            window_title = None

            category = self._categorize_app(app_name, window_title)

            return AppContext(
                app_name=app_name,
                window_title=window_title,
                app_category=category,
            )

        except ImportError:
            return AppContext(app_name="Unknown")

    def _get_linux_context(self) -> AppContext:
        """Get context on Linux using xdotool or wmctrl."""
        import subprocess

        app_name = "Unknown"
        window_title = None

        try:
            # Try xdotool first
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if result.returncode == 0:
                window_title = result.stdout.strip()

            # Get the window class (app name)
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowclassname"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if result.returncode == 0:
                app_name = result.stdout.strip()

        except (FileNotFoundError, subprocess.TimeoutExpired):
            # xdotool not available, try wmctrl
            try:
                result = subprocess.run(
                    ["wmctrl", "-l", "-p"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                # Parse wmctrl output (complex, simplified version)
                if result.returncode == 0 and result.stdout:
                    lines = result.stdout.strip().split("\n")
                    if lines:
                        parts = lines[0].split()
                        if len(parts) > 4:
                            window_title = " ".join(parts[4:])
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        category = self._categorize_app(app_name, window_title)

        return AppContext(
            app_name=app_name,
            window_title=window_title,
            app_category=category,
        )

    def _categorize_app(self, app_name: str, window_title: Optional[str] = None) -> Optional[str]:
        """
        Categorize an app based on its name and window title.

        Args:
            app_name: Name of the application
            window_title: Optional window title

        Returns:
            Category string or None
        """
        search_text = app_name.lower()
        if window_title:
            search_text += " " + window_title.lower()

        for keyword, category in self.APP_CATEGORIES.items():
            if keyword in search_text:
                return category

        return None

    @property
    def last_context(self) -> Optional[AppContext]:
        """Get the last detected context."""
        return self._last_context


# Global detector instance
_context_detector: Optional[ContextDetector] = None


def get_context_detector() -> ContextDetector:
    """Get the global context detector instance."""
    global _context_detector
    if _context_detector is None:
        _context_detector = ContextDetector()
    return _context_detector


def get_current_app_context() -> AppContext:
    """Convenience function to get current app context."""
    return get_context_detector().get_active_app()

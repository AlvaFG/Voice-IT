"""
Voice IT - Paste Handler
Handles clipboard operations and pasting text to active applications.
"""

import platform
import time
from typing import Optional

try:
    import pyperclip
    import pyautogui
except ImportError:
    pyperclip = None
    pyautogui = None


class PasteHandler:
    """
    Cross-platform paste handler for Voice IT.
    Copies text to clipboard and pastes it to the active application.
    """

    def __init__(self):
        """Initialize the paste handler."""
        if pyperclip is None or pyautogui is None:
            raise ImportError(
                "pyperclip or pyautogui not installed. "
                "Run: pip install pyperclip pyautogui"
            )

        self._system = platform.system()

        # Disable pyautogui failsafe for smoother operation
        pyautogui.FAILSAFE = False

    def paste_text(self, text: str, clear_after: bool = False) -> bool:
        """
        Paste text to the currently active application.

        Args:
            text: Text to paste
            clear_after: Whether to clear clipboard after pasting

        Returns:
            True if successful, False otherwise
        """
        print(f"[TRACE] paste_text called with {len(text)} chars")

        if not text:
            return False

        try:
            # Step 1: Copy to clipboard
            print("[TRACE] paste_text: Copying to clipboard...")
            pyperclip.copy(text)

            # Step 2: Wait for any hotkey keys to be released
            # This prevents interference when user just released Ctrl+Win
            print("[TRACE] paste_text: Waiting 300ms for keys to release...")
            time.sleep(0.3)

            # Step 3: Paste using platform-specific shortcut
            print("[TRACE] paste_text: Sending Ctrl+V...")
            if self._system == "Darwin":  # macOS
                pyautogui.hotkey("command", "v")
            else:  # Windows and Linux
                pyautogui.hotkey("ctrl", "v")

            # Step 4: Small delay after paste
            print("[TRACE] paste_text: Done, waiting 100ms...")
            time.sleep(0.1)

            # Step 5: Optional - clear clipboard after pasting
            if clear_after:
                time.sleep(0.5)
                pyperclip.copy("")

            print("[TRACE] paste_text: Complete")
            return True

        except Exception as e:
            print(f"Error pasting text: {e}")
            return False

    def copy_to_clipboard(self, text: str) -> bool:
        """
        Copy text to clipboard without pasting.

        Args:
            text: Text to copy

        Returns:
            True if successful, False otherwise
        """
        try:
            pyperclip.copy(text)
            return True
        except Exception as e:
            print(f"Error copying to clipboard: {e}")
            return False

    def get_clipboard(self) -> Optional[str]:
        """
        Get current clipboard contents.

        Returns:
            Clipboard text or None if empty/error
        """
        try:
            return pyperclip.paste()
        except Exception as e:
            print(f"Error getting clipboard: {e}")
            return None

    def copy_selected_text(self) -> Optional[str]:
        """
        Copy currently selected text from the active application.

        Uses Ctrl+C (or Cmd+C on macOS) to copy selection to clipboard,
        then retrieves the clipboard contents.

        Returns:
            Selected text or None if nothing selected/error
        """
        try:
            # Save current clipboard contents
            original_clipboard = self.get_clipboard() or ""

            # Small delay to ensure we don't interfere with other operations
            time.sleep(0.05)

            # Send copy command
            if self._system == "Darwin":  # macOS
                pyautogui.hotkey("command", "c")
            else:  # Windows and Linux
                pyautogui.hotkey("ctrl", "c")

            # Wait for clipboard to update
            time.sleep(0.15)

            # Get the copied text
            copied_text = self.get_clipboard()

            # Check if we got new content (different from original)
            if copied_text and copied_text != original_clipboard:
                return copied_text

            # If clipboard unchanged, might be empty selection
            # Restore original clipboard and return None
            if original_clipboard:
                pyperclip.copy(original_clipboard)

            return None

        except Exception as e:
            print(f"Error copying selected text: {e}")
            return None

    def type_text(self, text: str, interval: float = 0.01) -> bool:
        """
        Type text character by character (fallback for apps that block paste).

        Args:
            text: Text to type
            interval: Delay between characters in seconds

        Returns:
            True if successful, False otherwise
        """
        try:
            # Only works for ASCII characters
            pyautogui.typewrite(text, interval=interval)
            return True
        except Exception as e:
            print(f"Error typing text: {e}")
            return False


# Global paste handler instance
_paste_handler: Optional[PasteHandler] = None


def get_paste_handler() -> PasteHandler:
    """Get the global paste handler instance."""
    global _paste_handler
    if _paste_handler is None:
        _paste_handler = PasteHandler()
    return _paste_handler

"""
Voice IT - System Tray
Handles the system tray icon and menu.
"""

import threading
from typing import Callable, Optional

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None
    Image = None

from voice_it.storage.config import get_config

# Colors for tray icons (Voice IT brand colors)
TRAY_COLORS = {
    "idle": "#5A5A5A",        # Grey - ready
    "recording": "#FF3355",    # Red - recording
    "processing": "#FFB800",   # Yellow - processing
    "success": "#00D9FF",      # Cyan - success (brand color)
    "error": "#FF3355",        # Red - error
    "accent": "#00D9FF",       # Cyan accent
}


class SystemTray:
    """
    System tray icon for Voice IT.
    Shows status and provides quick access to features.
    """

    # Icon states
    STATE_IDLE = "idle"
    STATE_RECORDING = "recording"
    STATE_PROCESSING = "processing"
    STATE_SUCCESS = "success"
    STATE_ERROR = "error"

    def __init__(
        self,
        on_open: Optional[Callable[[], None]] = None,
        on_settings: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
        on_provider_change: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the system tray.

        Args:
            on_open: Callback to open main window
            on_settings: Callback to open settings
            on_exit: Callback to exit application
            on_provider_change: Callback(provider_id) when provider is switched
        """
        if pystray is None or Image is None:
            raise ImportError(
                "pystray or Pillow not installed. "
                "Run: pip install pystray Pillow"
            )

        self.on_open = on_open
        self.on_settings = on_settings
        self.on_exit = on_exit
        self.on_provider_change = on_provider_change
        self.config = get_config()

        self._state = self.STATE_IDLE
        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

        # Pre-generate icons for each state
        self._icons = {
            self.STATE_IDLE: self._create_icon(TRAY_COLORS["idle"]),
            self.STATE_RECORDING: self._create_icon(TRAY_COLORS["recording"]),
            self.STATE_PROCESSING: self._create_icon(TRAY_COLORS["processing"]),
            self.STATE_SUCCESS: self._create_icon(TRAY_COLORS["success"]),
            self.STATE_ERROR: self._create_icon(TRAY_COLORS["error"]),
        }

    def _create_icon(self, color: str, size: int = 64) -> Image.Image:
        """
        Create a waveform icon with the specified color.

        Voice IT brand icon: Sound wave bars in a circle.

        Args:
            color: Hex color string
            size: Icon size in pixels

        Returns:
            PIL Image
        """
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Parse hex color
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        bar_color = (r, g, b, 255)

        # Dark background circle
        bg_color = (26, 26, 26, 255)  # #1A1A1A
        padding = 2
        draw.ellipse(
            [padding, padding, size - padding, size - padding],
            fill=bg_color,
            outline=bar_color,
            width=2
        )

        # Draw waveform bars (sound visualization)
        center_y = size // 2
        bar_width = size // 10
        bar_spacing = bar_width + 2

        # Bar heights (creates waveform pattern)
        bar_heights = [
            size * 0.35,  # tall
            size * 0.55,  # tallest
            size * 0.35,  # tall
            size * 0.20,  # short
        ]

        # Calculate starting x to center the bars
        total_width = len(bar_heights) * bar_spacing - 2
        start_x = (size - total_width) // 2

        for i, height in enumerate(bar_heights):
            x = start_x + i * bar_spacing
            y1 = center_y - height // 2
            y2 = center_y + height // 2

            # Draw rounded bar
            draw.rounded_rectangle(
                [x, y1, x + bar_width, y2],
                radius=bar_width // 2,
                fill=bar_color
            )

        return image

    def _create_menu(self) -> pystray.Menu:
        """Create the tray menu."""

        def is_groq_active(item):
            return self.config.get("provider.active", "groq") == "groq"

        def is_chatgpt_active(item):
            return self.config.get("provider.active", "groq") == "chatgpt"

        def is_gemini_active(item):
            return self.config.get("provider.active", "groq") == "gemini"

        def is_grok_active(item):
            return self.config.get("provider.active", "groq") == "grok"

        return pystray.Menu(
            pystray.MenuItem("Open Voice IT", self._on_open_click, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Start Recording", self._on_record_click),
            pystray.MenuItem("View History", self._on_history_click),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Provider",
                pystray.Menu(
                    pystray.MenuItem(
                        "Groq (Whisper)",
                        lambda icon, item: self._switch_provider("groq"),
                        checked=is_groq_active,
                        radio=True,
                    ),
                    pystray.MenuItem(
                        "ChatGPT",
                        lambda icon, item: self._switch_provider("chatgpt"),
                        checked=is_chatgpt_active,
                        radio=True,
                    ),
                    pystray.MenuItem(
                        "Gemini",
                        lambda icon, item: self._switch_provider("gemini"),
                        checked=is_gemini_active,
                        radio=True,
                    ),
                    pystray.MenuItem(
                        "Grok (xAI)",
                        lambda icon, item: self._switch_provider("grok"),
                        checked=is_grok_active,
                        radio=True,
                    ),
                )
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings", self._on_settings_click),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit Voice IT", self._on_exit_click),
        )

    def _on_open_click(self, icon, item):
        """Handle Open menu click."""
        if self.on_open:
            self.on_open()

    def _on_record_click(self, icon, item):
        """Handle Start Recording menu click."""
        # TODO: Trigger recording from tray
        pass

    def _on_history_click(self, icon, item):
        """Handle View History menu click."""
        if self.on_open:
            self.on_open()
        # TODO: Navigate to history view

    def _switch_provider(self, provider_id: str):
        """
        Switch to a different provider.

        Args:
            provider_id: Provider to switch to ("claude", "chatgpt", "gemini")
        """
        # Check if provider is connected
        is_connected = self.config.get(f"provider.connected.{provider_id}", False)

        if not is_connected:
            print(f"Warning: {provider_id} is not connected. Please connect first.")
            return

        # Set active provider
        self.config.set("provider.active", provider_id)
        print(f"Switched to provider: {provider_id}")

        # Update menu (refresh checkmarks)
        if self._icon:
            self._icon.update_menu()

        # Notify callback
        if self.on_provider_change:
            self.on_provider_change(provider_id)

    def _on_provider_click(self, icon, item):
        """Handle Provider menu click (deprecated, use _switch_provider)."""
        pass

    def _on_settings_click(self, icon, item):
        """Handle Settings menu click."""
        if self.on_settings:
            self.on_settings()

    def _on_exit_click(self, icon, item):
        """Handle Exit menu click."""
        if self.on_exit:
            self.on_exit()

    def set_state(self, state: str):
        """
        Set the tray icon state.

        Args:
            state: One of STATE_IDLE, STATE_RECORDING, STATE_PROCESSING,
                   STATE_SUCCESS, STATE_ERROR
        """
        if state not in self._icons:
            state = self.STATE_IDLE

        self._state = state

        if self._icon:
            self._icon.icon = self._icons[state]

            # Update tooltip
            tooltips = {
                self.STATE_IDLE: "Voice IT - Ready",
                self.STATE_RECORDING: "Voice IT - Recording...",
                self.STATE_PROCESSING: "Voice IT - Processing...",
                self.STATE_SUCCESS: "Voice IT - Done!",
                self.STATE_ERROR: "Voice IT - Error",
            }
            self._icon.title = tooltips.get(state, "Voice IT")

    def start(self):
        """Start the system tray icon."""
        self._icon = pystray.Icon(
            name="voice_it",
            icon=self._icons[self.STATE_IDLE],
            title="Voice IT - Ready",
            menu=self._create_menu(),
        )

        # Run in background thread
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

        print("System tray started.")

    def stop(self):
        """Stop the system tray icon."""
        if self._icon:
            self._icon.stop()
            self._icon = None

        print("System tray stopped.")

    @property
    def state(self) -> str:
        """Get the current tray state."""
        return self._state

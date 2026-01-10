"""
Voice IT - Audio Engine
Handles microphone recording and audio processing.
"""

import io
import wave
import threading
from typing import Optional, Callable, List
from pathlib import Path
import tempfile

try:
    import numpy as np
    import sounddevice as sd
except ImportError:
    np = None
    sd = None


class AudioEngine:
    """
    Cross-platform audio recording engine.
    Uses sounddevice for recording audio from the microphone.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        dtype: str = "int16",
        device: Optional[str] = None,
    ):
        """
        Initialize the audio engine.

        Args:
            sample_rate: Audio sample rate in Hz (default: 16000)
            channels: Number of audio channels (default: 1 for mono)
            dtype: Audio data type (default: int16)
            device: Specific audio device to use (default: system default)
        """
        if sd is None or np is None:
            raise ImportError(
                "Audio dependencies not installed. "
                "Run: pip install sounddevice numpy"
            )

        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.device = device

        # Recording state
        self._recording = False
        self._audio_buffer: List[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()

        # Callbacks
        self._on_audio_level: Optional[Callable[[float], None]] = None

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback function for audio stream."""
        if status:
            print(f"Audio status: {status}")

        if self._recording:
            with self._lock:
                self._audio_buffer.append(indata.copy())

            # Calculate audio level for visualization
            if self._on_audio_level:
                level = np.abs(indata).mean()
                self._on_audio_level(float(level))

    def start_recording(self, on_audio_level: Optional[Callable[[float], None]] = None):
        """
        Start recording audio from the microphone.

        Args:
            on_audio_level: Optional callback for audio level updates (0.0-1.0)
        """
        if self._recording:
            return

        self._on_audio_level = on_audio_level
        self._audio_buffer = []
        self._recording = True

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                device=self.device,
                callback=self._audio_callback,
            )
            self._stream.start()
            print(f"Recording started (device: {self.device or 'default'})")
        except Exception as e:
            self._recording = False
            print(f"Error starting recording: {e}")
            raise

    def stop_recording(self) -> Optional[bytes]:
        """
        Stop recording and return the recorded audio data.

        Returns:
            Audio data as bytes (WAV format), or None if no audio recorded
        """
        if not self._recording:
            return None

        self._recording = False

        # Stop and close the stream
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        # Get recorded audio
        with self._lock:
            if not self._audio_buffer:
                return None

            audio_data = np.concatenate(self._audio_buffer, axis=0)
            self._audio_buffer = []

        # Convert to WAV bytes
        wav_bytes = self._to_wav_bytes(audio_data)
        print(f"Recording stopped ({len(wav_bytes)} bytes)")

        return wav_bytes

    def _to_wav_bytes(self, audio_data: np.ndarray) -> bytes:
        """Convert numpy audio array to WAV format bytes."""
        buffer = io.BytesIO()

        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit audio = 2 bytes
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data.tobytes())

        return buffer.getvalue()

    def save_to_file(self, audio_data: bytes, path: Optional[Path] = None) -> Path:
        """
        Save audio data to a WAV file.

        Args:
            audio_data: Audio data as bytes
            path: Optional path to save to (uses temp file if not provided)

        Returns:
            Path to the saved file
        """
        if path is None:
            fd, path = tempfile.mkstemp(suffix=".wav", prefix="voice_it_")
            path = Path(path)

        with open(path, "wb") as f:
            f.write(audio_data)

        return path

    def get_devices(self) -> List[dict]:
        """
        Get list of available audio input devices.

        Returns:
            List of device info dictionaries
        """
        devices = []
        try:
            for i, device in enumerate(sd.query_devices()):
                if device["max_input_channels"] > 0:
                    devices.append({
                        "index": i,
                        "name": device["name"],
                        "channels": device["max_input_channels"],
                        "sample_rate": device["default_samplerate"],
                    })
        except Exception as e:
            print(f"Error querying devices: {e}")

        return devices

    def set_device(self, device: Optional[str]) -> None:
        """
        Set the audio input device.

        Args:
            device: Device name, index, or None for default
        """
        self.device = device

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._recording

    def cleanup(self):
        """Cleanup audio resources."""
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._recording = False
        self._audio_buffer = []

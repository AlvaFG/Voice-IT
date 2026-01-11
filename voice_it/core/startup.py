"""
Voice IT - Windows Startup Manager
Handles auto-start with Windows functionality.
"""

import sys
import os
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    import winreg


REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "VoiceIT"


def get_executable_path() -> str:
    """
    Get the path to the executable.
    Returns the path to VoiceIT.exe if running as frozen executable,
    otherwise returns the Python command to run the module.
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return sys.executable
    else:
        # Running as Python script - use pythonw to avoid console
        python_exe = sys.executable
        if python_exe.endswith("python.exe"):
            pythonw = python_exe.replace("python.exe", "pythonw.exe")
            if Path(pythonw).exists():
                python_exe = pythonw

        module_path = Path(__file__).parent.parent.parent
        return f'"{python_exe}" -m voice_it'


def is_startup_enabled() -> bool:
    """
    Check if the application is set to start with Windows.

    Returns:
        True if startup is enabled, False otherwise.
    """
    if sys.platform != "win32":
        return False

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_KEY,
            0,
            winreg.KEY_READ
        )
        try:
            winreg.QueryValueEx(key, APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False


def enable_startup(start_minimized: bool = True) -> bool:
    """
    Enable auto-start with Windows.

    Args:
        start_minimized: If True, app starts in background (minimized to tray).

    Returns:
        True if successful, False otherwise.
    """
    if sys.platform != "win32":
        return False

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_KEY,
            0,
            winreg.KEY_SET_VALUE
        )

        exe_path = get_executable_path()

        # Add --background flag to start minimized
        if start_minimized:
            if getattr(sys, 'frozen', False):
                command = f'"{exe_path}" --background'
            else:
                command = f'{exe_path} --background'
        else:
            if getattr(sys, 'frozen', False):
                command = f'"{exe_path}"'
            else:
                command = exe_path

        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Error enabling startup: {e}")
        return False


def disable_startup() -> bool:
    """
    Disable auto-start with Windows.

    Returns:
        True if successful, False otherwise.
    """
    if sys.platform != "win32":
        return False

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_KEY,
            0,
            winreg.KEY_SET_VALUE
        )

        try:
            winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass  # Already removed

        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Error disabling startup: {e}")
        return False


def set_startup_enabled(enabled: bool, start_minimized: bool = True) -> bool:
    """
    Set whether the application should start with Windows.

    Args:
        enabled: True to enable, False to disable.
        start_minimized: If True, app starts in background.

    Returns:
        True if successful, False otherwise.
    """
    if enabled:
        return enable_startup(start_minimized)
    else:
        return disable_startup()

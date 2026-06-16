"""
Voice IT - Main Entry Point
Run with: python -m voice_it
         python -m voice_it --background  (start minimized to tray)
"""

import sys
import platform
import logging
import argparse

from voice_it import __version__, __app_name__


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Voice IT - Voice-to-text transcription app"
    )
    parser.add_argument(
        "--background",
        action="store_true",
        help="Start minimized to system tray (no window)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging"
    )
    return parser.parse_args()


def main():
    """Main entry point for Voice IT."""
    # Check Python version
    if sys.version_info < (3, 10):
        print("Error: Voice IT requires Python 3.10 or higher")
        sys.exit(1)

    # Parse arguments
    args = parse_args()

    # Configure logging once for the whole app. Debug-level logs (the former
    # [DEBUG]/[TRACE] prints) stay silent unless --debug is passed.
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Print startup info
    print(f"{__app_name__} v{__version__}")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    if args.background:
        print("Mode: Background (minimized to tray)")
    print()

    # Import and run the application
    try:
        from voice_it.app import VoiceITApp
        app = VoiceITApp()
        app.run(start_hidden=args.background)
    except ImportError as e:
        print(f"Error: Missing dependency - {e}")
        print("Run: pip install -r requirements.txt")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

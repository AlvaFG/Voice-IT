"""
Voice IT - Main Entry Point
Run with: python -m voice_it
"""

import sys
import platform


def main():
    """Main entry point for Voice IT."""
    # Check Python version
    if sys.version_info < (3, 10):
        print("Error: Voice IT requires Python 3.10 or higher")
        sys.exit(1)

    # Print startup info
    print(f"Voice IT v0.1.0")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    print()

    # Import and run the application
    try:
        from voice_it.app import VoiceITApp
        app = VoiceITApp()
        app.run()
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

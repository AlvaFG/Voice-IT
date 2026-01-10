# Voice IT

> Voice-to-text transcription app for Windows. Hold a hotkey, speak, and paste text anywhere.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-Windows-blue.svg)]()

---

## What is Voice IT?

Voice IT is a **free, open-source voice dictation tool** that converts your speech to text instantly. Press and hold a hotkey, speak, and the transcribed text is pasted wherever your cursor is.

**Key Features:**
- Hold `Ctrl+Win` to record, release to transcribe and paste
- Powered by AI (Whisper, Gemini) for 95%+ accuracy
- Works in any application
- Multiple AI providers with automatic failover
- System tray app - runs in background
- 100% local storage - your data stays on your machine

---

## Quick Demo

```
1. Open any text field (email, Word, browser, etc.)
2. Hold Ctrl+Win and speak: "Hello, this is a test message"
3. Release the keys
4. Text appears: "Hello, this is a test message."
```

---

## Why Use AI for Transcription?

| Feature | With AI (Voice IT) | Traditional STT |
|---------|-------------------|-----------------|
| **Accuracy** | 95-99% even with noise | 70-85% in ideal conditions |
| **Languages** | 50+ auto-detected | Manual configuration |
| **Accents** | Excellent adaptation | Poor recognition |
| **Background noise** | Smart filtering | Fails frequently |
| **Technical jargon** | Learns from context | Limited dictionaries |
| **Punctuation** | Automatic & intelligent | Manual or basic |

---

## Quick Setup: Get Your Free API Key (2 minutes)

We recommend **Groq** because:
- 100% FREE (no credit card needed)
- 14,400 transcriptions per day
- Fastest transcription speed
- Best quality (uses Whisper Large v3)

### How to get your Groq API Key:

1. Go to **[console.groq.com](https://console.groq.com)**
2. Click "Sign Up" (use Google or GitHub for fastest setup)
3. Once logged in, go to **"API Keys"** in the left menu
4. Click **"Create API Key"**
5. Copy the key and paste it in Voice IT settings

That's it! You're ready to use Voice IT.

---

## Other Providers (Optional)

| Provider | Cost | Free Limit | Speed |
|----------|------|------------|-------|
| **Groq** | Free | 14,400/day | Fastest |
| **Gemini** | Free | 15/min | Fast |
| **ChatGPT** | $0.006/min | $5 credit | Slower |
| **Grok** | $5/month | None | Fast |

<details>
<summary>How to get other API keys</summary>

#### Google Gemini (Free Backup)
1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Sign in with Google account
3. Click "Get API Key" -> "Create API Key"
4. Copy the key

#### OpenAI ChatGPT (Paid)
1. Go to [platform.openai.com](https://platform.openai.com)
2. Create account and add payment method
3. Go to "API Keys" -> "Create new secret key"
4. Copy the key

#### Grok / xAI
1. Go to [console.x.ai](https://console.x.ai)
2. Request API access
3. Once approved, create API key

</details>

---

## Installation

### Option 1: Run from Source

```bash
# Clone repository
git clone https://github.com/yourusername/voice-it.git
cd voice-it

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run
python -m voice_it
```

### Option 2: Build Executable

```bash
# After cloning and installing dependencies
build.bat
```

The executable will be at `dist/VoiceIT.exe`

### Option 3: Download Release

Download the latest `.exe` from [Releases](https://github.com/yourusername/voice-it/releases).

---

## Desktop Shortcut & Auto-Start

### Create Desktop Shortcut

**If using the .exe:**
1. Right-click on `VoiceIT.exe`
2. Select "Create shortcut"
3. Move the shortcut to your Desktop

**If running from source:**
1. Right-click on Desktop → New → Shortcut
2. Enter the path:
   ```
   pythonw -m voice_it
   ```
   Or the full path:
   ```
   C:\path\to\venv\Scripts\pythonw.exe -m voice_it
   ```
3. Name it "Voice IT"
4. (Optional) Right-click shortcut → Properties → Change Icon → Browse to `voice_it\ui\assets\icon.ico`

### Auto-Start with Windows

**Method 1: Startup Folder**
1. Press `Win + R`, type `shell:startup`, press Enter
2. Copy your Voice IT shortcut into this folder
3. Done! Voice IT will start when Windows boots

**Method 2: Task Scheduler (for .exe)**
1. Open Task Scheduler
2. Create Basic Task → Name: "Voice IT"
3. Trigger: "When I log on"
4. Action: "Start a program" → Browse to `VoiceIT.exe`
5. Finish

---

## Usage

### Basic Dictation

1. **Start Voice IT** - App icon appears in system tray
2. **Click tray icon** to open settings
3. **Enter your API key** in Settings -> Providers -> Select provider -> Enter key
4. **Start dictating**:
   - Place cursor where you want text
   - Hold `Ctrl + Win`
   - Speak clearly
   - Release keys
   - Text is pasted automatically

### Hotkeys

| Action | Hotkey |
|--------|--------|
| Dictation | `Ctrl + Win` (hold to record) |

### System Tray

- **Left click**: Open/hide main window
- **Right click**: Menu (Show, Settings, Exit)
- **X button**: Minimizes to tray (doesn't quit)
- **Exit**: Right-click tray -> Exit

---

## Configuration

Settings are stored in: `%LOCALAPPDATA%\Voice IT\config.yaml`

You can configure:
- Active AI provider
- Auto-failover between providers
- Audio input device

---

## System Requirements

| Requirement | Minimum |
|-------------|---------|
| OS | Windows 10+ |
| Python | 3.10+ (if running from source) |
| RAM | 4 GB |
| Internet | Required for AI transcription |
| Microphone | Any working microphone |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| UI | PyWebView (HTML/CSS/JS) |
| System Tray | pystray |
| Audio | sounddevice |
| Hotkeys | pynput |
| AI Providers | groq, openai, google-generativeai |
| Storage | SQLite + YAML |
| Auth | keyring (secure credential storage) |

---

## Troubleshooting

### "No provider connected"
- Go to Settings and enter your API key for at least one provider

### Hotkey not working
- Make sure Voice IT is running (check system tray)
- Some apps may intercept `Ctrl+Win` - try running Voice IT as administrator

### Audio not recording
- Check Windows sound settings - make sure microphone is selected
- Grant microphone permissions to Python/Voice IT

### Transcription empty or wrong
- Speak clearly and at moderate pace
- Check your internet connection
- Try a different AI provider

---

## Project Structure

```
voice_it/
├── __main__.py          # Entry point
├── app.py               # Main orchestrator
├── core/                # Core functionality
│   ├── audio_engine.py  # Audio recording
│   ├── hotkey_manager.py# Hotkey listener
│   └── paste_handler.py # Clipboard/paste
├── features/
│   └── dictation.py     # Dictation flow
├── providers/           # AI providers
│   ├── groq_provider.py
│   ├── chatgpt_provider.py
│   ├── gemini_provider.py
│   └── grok_provider.py
├── storage/             # Data persistence
│   ├── auth_store.py    # Secure API key storage
│   ├── config.py        # Configuration
│   └── database.py      # History
└── ui/                  # User interface
    ├── bridge.py        # Python-JS bridge
    ├── window_manager.py
    ├── tray.py          # System tray
    └── web/             # HTML/CSS/JS
```

---

## Contributing

Contributions are welcome!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [Groq](https://groq.com) for blazing fast Whisper inference
- [OpenAI](https://openai.com) for Whisper model
- [Google](https://ai.google.dev) for Gemini
- [PyWebView](https://pywebview.flowrl.com) for desktop UI

---

**Made with voice, for voice.**

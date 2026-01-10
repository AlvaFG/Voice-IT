# Platform Support

## Current Status

| Platform | Status | Notes |
|----------|--------|-------|
| **Windows 10/11** | ✅ Fully supported | Tested and working |
| **macOS** | ❌ Not supported | Needs adaptation |
| **Linux** | ❌ Not supported | Needs adaptation |

---

## What's Needed for macOS Support

### 1. Hotkey Changes
- Replace `Ctrl + Win` with `Ctrl + Cmd` or `Cmd + Shift`
- File: `voice_it/core/hotkey_manager.py`

### 2. Remove Windows Dependencies
- `pywin32` → Not needed on macOS
- File: `requirements.txt` - already has platform condition

### 3. Taskbar Icon
- Remove Windows-specific icon code using `ctypes.windll`
- File: `voice_it/ui/window_manager.py`
- PyWebView handles icons differently on macOS

### 4. Auto-Start
macOS uses Launch Agents instead of Startup folder:
```bash
# Create: ~/Library/LaunchAgents/com.voiceit.plist
```

### 5. Permissions
macOS requires explicit permissions for:
- Microphone access
- Accessibility (for global hotkeys)
- Input monitoring

---

## What's Needed for Linux Support

### 1. Hotkey Changes
- Replace `Ctrl + Win` with `Ctrl + Alt` or `Super` key
- File: `voice_it/core/hotkey_manager.py`

### 2. Remove Windows Dependencies
- `pywin32` → Not needed on Linux
- May need `python3-xlib` for some features

### 3. System Tray
- `pystray` works on Linux but may need:
  - `libappindicator` (Ubuntu/Debian)
  - GTK or Qt backend

### 4. Auto-Start
Linux uses `.desktop` files:
```bash
# Create: ~/.config/autostart/voiceit.desktop
[Desktop Entry]
Type=Application
Name=Voice IT
Exec=python -m voice_it
Hidden=false
```

### 5. Audio
- May need `pulseaudio` or `pipewire` configured
- `sounddevice` should work but test audio input

---

## Contributing

If you want to add macOS or Linux support:

1. Fork the repository
2. Create a branch: `feature/macos-support` or `feature/linux-support`
3. Make the necessary changes
4. Test thoroughly on the target platform
5. Submit a Pull Request

### Testing Checklist
- [ ] App starts without errors
- [ ] Hotkey registers and works globally
- [ ] Audio recording works
- [ ] Transcription completes successfully
- [ ] Text pastes to active application
- [ ] System tray icon appears
- [ ] Auto-start works (optional)

---

## Resources

- [pynput documentation](https://pynput.readthedocs.io/) - Cross-platform hotkeys
- [PyWebView platforms](https://pywebview.flowrl.com/guide/installation.html) - Platform-specific setup
- [pystray](https://github.com/moses-palmer/pystray) - System tray support

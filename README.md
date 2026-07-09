# Crier

Press a hotkey to read your selected text aloud anywhere — natural local voice, fully offline.

Crier lives in your system tray. Select text in any window, hit the hotkey, and a small
control popup appears while a natural [Kokoro](https://github.com/thewh1teagle/kokoro-onnx)
neural voice reads it — all on-device, no cloud, no account.

## Features

- **Read anywhere** — select text in any app, press `Ctrl+Alt+R`.
- **Quick controls popup** — play/pause, stop, re-read, speed, and volume, right at your cursor.
- **Tray icon** — show the controls, open settings, check for updates, or quit.
- **Local & private** — Kokoro runs offline on your CPU; text never leaves your machine.
- **Single instance** — launching again just pops the controls back up.
- **Self-updating** — checks GitHub releases on startup (and on demand) and offers to update.
- **Settings** — voice, language, hotkeys, GPU toggle, auto-update, start-at-login.

## Run from source (development)

Use **Python 3.10–3.12** (Kokoro's dependencies don't ship 3.13 wheels yet).

```bash
py -3.12 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m crier
```

On first run, Crier downloads the Kokoro model (~330 MB) into
`%LOCALAPPDATA%\Crier\models`. That's the only network step, and it's a one-time thing.

## Build the installer

```bash
pip install pyinstaller pillow
python build/make_icon.py          # generates crier/resources/crier.ico
pyinstaller build/crier.spec       # -> dist/Crier/Crier.exe
iscc build/installer.iss           # -> dist/Crier-Setup-<version>.exe  (needs Inno Setup)
```

Or just push a tag (`git tag v0.1.0 && git push --tags`) and the GitHub Actions
workflow builds the installer and attaches it to the release. The self-updater
looks for that `.exe` asset.

## Hotkeys (default)

| Action | Shortcut |
|---|---|
| Read selection | `Ctrl+Alt+R` |
| Stop | `Ctrl+Alt+S` |

Change them in Settings (tray icon → Settings). Format is pynput style, e.g. `<ctrl>+<alt>+r`.

## Notes & known rough edges

- **Speed** is a synthesis parameter, so changing the speed slider re-generates the
  current selection (there's a short debounce). Volume is applied live.
- **GPU (DirectML)** is an experimental toggle. Kokoro currently errors on DirectML
  (a ConvTranspose op issue), so Crier smoke-tests it at load and silently falls back
  to CPU. CPU is real-time for this model anyway.
- **Corporate machines**: the self-updater downloads and runs an installer, which some
  managed environments block. The manual "Check for updates" falls back to opening the
  releases page if no installer asset is found.

## License

MIT

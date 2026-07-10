# Crier

Press a hotkey to read your selected text aloud anywhere — natural local voice, fully offline.

Crier lives in your system tray. Select text in any window, hit the hotkey, and a small
control popup appears while a natural [Kokoro](https://github.com/thewh1teagle/kokoro-onnx)
neural voice reads it — all on-device, no cloud, no account.

## Features

- **Read anywhere** — select text in any app, press `Ctrl+Alt+R`.
- **Screen grab → speech** — press `Ctrl+Alt+C`, drag a box around any on-screen text (even
  text you can't select, like images or disabled-selection web pages), and Crier reads it
  aloud. Uses Windows' built-in OCR engine - no model download, no extra install. Press
  `Escape` at any point to back out without capturing anything.
- **Smart hotkey** — press `Ctrl+Alt+S` and Crier figures out which of the above you meant:
  reads the selection if there is one, otherwise starts a screen grab.
- **Quick controls popup** — one combined "Read / Screen Grab" button, icon transport
  buttons, a click/drag seek bar, speed, and volume, docked in a screen corner (or
  wherever you drag it).
- **Tray icon** — show the controls, screen grab, open settings, check for updates, or quit.
- **Local & private** — Kokoro runs offline on your CPU; text never leaves your machine.
- **Single instance** — launching again just pops the controls back up.
- **Self-updating** — checks the git remote on startup (and on demand), then pulls and
  restarts in place.
- **Settings** — voice, language, hotkeys, GPU toggle, auto-update, start-at-login.

## Setup

Crier runs from a plain git checkout — no installer, no frozen exe. That also sidesteps
Windows SmartScreen blocking an unsigned downloaded `.exe`, which some corporate-managed
machines won't let you override.

Use **Python 3.10–3.12** (Kokoro's dependencies don't ship 3.13 wheels yet).

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m crier
```

On first run, Crier downloads the Kokoro model (~330 MB) into
`%LOCALAPPDATA%\Crier\models`. That's the only network step, and it's a one-time thing.

## Running it day to day

- **Manual launch**: double-click [run-crier.bat](run-crier.bat).
- **Start at login**: either copy [run-crier-hidden.vbs](run-crier-hidden.vbs) into your
  Startup folder (`Win+R` → `shell:startup`), or just check "start at login" in Crier's
  own Settings dialog once it's running.

Both launch through `pythonw.exe` (no console window), which is also why they're not
subject to the same SmartScreen check a downloaded `.exe` would be.

## Updating

The tray menu's "Check for updates" (and the auto-update-on-startup setting) run
`git fetch` against `origin/main`, and if there's something new, pull it in with
`git pull --ff-only`, reinstall `requirements.txt`, and restart. No download, nothing
to sign, nothing for SmartScreen to block.

## Hotkeys (default)

| Action | Shortcut |
|---|---|
| Read selection | `Ctrl+Alt+R` |
| Stop | `Ctrl+Alt+X` |
| Screen grab → speech | `Ctrl+Alt+C` |
| Smart (selection, else screen grab) | `Ctrl+Alt+S` |

Change them in Settings (tray icon → Settings). Format is pynput style, e.g. `<ctrl>+<alt>+r`.

## Notes & known rough edges

- **Speed** is a synthesis parameter, so changing the speed slider re-generates the
  current selection (there's a short debounce). Volume is applied live.
- **GPU (DirectML)** is an experimental toggle. Kokoro currently errors on DirectML
  (a ConvTranspose op issue), so Crier smoke-tests it at load and silently falls back
  to CPU. CPU is real-time for this model anyway.
- **Updating requires `git` on PATH** and a clean fast-forward from `origin/main` -
  if you've made local edits that conflict, `git pull --ff-only` will fail and the
  update dialog reports it rather than clobbering your changes.
- **First read/grab of each session pays a one-time model-load cost** (a couple of
  seconds), which `App.start()` pays proactively in the background right after launch
  rather than on your first Read Selection. After that, synthesis is chunked and
  streamed - playback starts on the first sentence or two while the rest keeps
  synthesizing in the background, rather than waiting for the whole selection.

## License

MIT

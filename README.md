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
- **Pluggable voice providers** — Settings > Voice has a provider dropdown. Kokoro (local,
  offline, free) is the default; OpenAI (cloud, paid, needs your own API key) is also
  built in. Each provider gets its own settings panel (API key, voice, tone, etc.) that
  only shows up when it's selected.
- **Settings** — a Voice tab (provider + that provider's own settings) and a General tab
  (hotkeys, auto-update, start-at-login).

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

## Voice providers

Crier's TTS backend is pluggable - `crier/providers/` has one module per provider,
each exposing an `Engine` (does the actual synthesis) and a `SettingsPanel` (the fields
Settings > Voice shows when that provider is selected). To add another one (ElevenLabs,
Azure, whatever), drop a new module in there implementing the same shape and register it
in `crier/providers/__init__.py` - nothing else needs to change.

- **Kokoro** (default) - runs locally on your CPU, fully offline, no account or cost.
- **OpenAI** (`gpt-4o-mini-tts`) - cloud-based, needs your own API key from
  [platform.openai.com](https://platform.openai.com/api-keys), and bills your OpenAI
  account per character synthesized. Chosen over ElevenLabs mainly on cost - OpenAI's
  per-character API pricing is meaningfully cheaper for this kind of casual/occasional
  reading use, though ElevenLabs is often considered to have an edge on voice
  expressiveness. Supports a free-text "tone" field (e.g. "calm and professional") that
  OpenAI's model uses to steer delivery style - Kokoro has no equivalent since Kokoro's
  API only exposes voice/speed/language as tunables.

Switching providers in Settings takes effect on your next read (it doesn't hot-swap
mid-playback). The popup's own speed/volume controls apply to whichever provider is
active, unchanged.

**Caveat:** the OpenAI integration is built from documented API behavior, not tested
against a live key (this project doesn't have one) - the model name, `instructions`
(tone) parameter, and `response_format="pcm"` handling are all this build's best current
understanding. If something errors or sounds off, the returned message should say why;
worth double-checking against OpenAI's current docs if so.

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

- **Two independent speed controls.** Settings > Voice has the active provider's own
  synthesis speed (Kokoro: 0.5x-2.0x, its hard limit) - a voice-quality setting that
  doesn't touch anything already playing. The popup's speed control (0.5x-3.0x, in 0.1x
  steps) is a separate live playback control: it takes whatever the provider already
  produced and stretches or compresses it in real time using a pitch-preserving
  time-scale algorithm (WSOLA), so fast/slow playback doesn't sound like a chipmunk or a
  record played too slow. Volume is also applied live. Neither control ever triggers a
  resynthesis. Past ~3x, though, any time-scale algorithm runs into a fundamental
  intelligibility floor regardless of tuning - that's why the popup caps there.
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

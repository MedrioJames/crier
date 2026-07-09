"""Paths, identifiers, and download URLs used across Crier."""

import os
from pathlib import Path

APP_NAME = "Crier"
ORG_NAME = "MedrioJames"

# Kokoro model assets. These are downloaded on first run so the installer stays small.
# If these URLs ever move, change them here (or point them at your own mirror).
MODEL_FILE = "kokoro-v1.0.onnx"
VOICES_FILE = "voices-v1.0.bin"
MODEL_URL = "https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/kokoro-v1.0.onnx"
VOICES_URL = "https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/voices-v1.0.bin"


def data_dir() -> Path:
    """Per-user writable directory, e.g. %LOCALAPPDATA%\\Crier."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    d = Path(base) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def models_dir() -> Path:
    d = data_dir() / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def model_paths():
    md = models_dir()
    return md / MODEL_FILE, md / VOICES_FILE


def resource_path(rel: str) -> str:
    """Resolve a bundled resource relative to the repo root."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def icon_path() -> str:
    p = Path(resource_path(os.path.join("crier", "resources", "crier.ico")))
    return str(p) if p.exists() else ""

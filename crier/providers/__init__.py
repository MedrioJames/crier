"""Voice provider registry. Each provider module exposes:

    PROVIDER_ID    - short string key, matches settings.voice_provider
    DISPLAY_NAME   - shown in the Settings dialog's provider dropdown
    Engine         - class(settings); .load(); .synthesize_chunk(text, pause_after=0.0)
                     -> (samples: np.ndarray float32, sample_rate: int); .backend (str,
                     for status messages)
    SettingsPanel  - QWidget(settings) with .apply_to_settings(settings)

To add a new provider: drop a module in this package implementing the above,
then add it to PROVIDERS below.
"""

from . import kokoro, openai

PROVIDERS = {
    kokoro.PROVIDER_ID: kokoro,
    openai.PROVIDER_ID: openai,
}

DEFAULT_PROVIDER_ID = kokoro.PROVIDER_ID


def get_provider(provider_id: str):
    return PROVIDERS.get(provider_id, PROVIDERS[DEFAULT_PROVIDER_ID])

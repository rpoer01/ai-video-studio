import whisper


_WHISPER_MODELS = {}


def get_whisper_model(model_name: str):
    """Reuse Whisper models within the running app process."""
    key = model_name or "base"
    if key not in _WHISPER_MODELS:
        _WHISPER_MODELS[key] = whisper.load_model(key)
    return _WHISPER_MODELS[key]

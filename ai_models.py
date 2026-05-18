import whisper
import assemblyai as aai
import os

_WHISPER_MODELS = {}

# AssemblyAI Configuration
aai.settings.api_key = "350bc0bb49d943768b559c72b0c74922"

def get_whisper_model(model_name: str):
    """Reuse Whisper models within the running app process."""
    key = model_name or "base"
    if key not in _WHISPER_MODELS:
        _WHISPER_MODELS[key] = whisper.load_model(key)
    return _WHISPER_MODELS[key]

def transcribe_with_assemblyai(audio_path: str, language: str = None):
    """Transcribe using AssemblyAI for better word-level timestamps."""
    # If no language is provided, we enable auto-detection
    config = aai.TranscriptionConfig(
        language_code=language if language else None,
        language_detection=True if not language else False
    )
    
    transcriber = aai.Transcriber()
    print(f"[*] AssemblyAI: Uploading and transcribing {os.path.basename(audio_path)}...")
    transcript = transcriber.transcribe(audio_path, config)
    
    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"AssemblyAI Transcription failed: {transcript.error}")
        
    # Process words into sentences for context
    segments = []
    sentences = transcript.get_sentences()
    
    for s in sentences:
        sentence_words = []
        for w in s.words:
            sentence_words.append({
                "word": w.text,
                "start": w.start / 1000.0,
                "end": w.end / 1000.0,
                "confidence": w.confidence
            })
        
        if sentence_words:
            segments.append({
                "text": s.text,
                "start": s.start / 1000.0,
                "end": s.end / 1000.0,
                "words": sentence_words
            })
            
    return {
        "text": transcript.text,
        "segments": segments,
        "language": transcript.json_response.get("language_code", "th")
    }

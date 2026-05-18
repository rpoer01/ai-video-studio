import os

from moviepy import VideoFileClip

import ai_models
import highlight_engine


def cut_highlight_video(
    video_path: str,
    model_name: str = "base",
    language: str | None = None,
    aspect_ratio: str = "9:16",
    target_duration: float = 60.0,
    category: str = "Auto",
    audio_threshold: float = 2.5,
) -> dict:
    """Transcribe, detect, plan, and render a highlight clip close to target_duration."""
    print(f"[*] Analyzing video with AssemblyAI for highlight detection...")
    try:
        transcript = ai_models.transcribe_with_assemblyai(video_path, language=language)
    except Exception as e:
        print(f"[!] AssemblyAI failed for highlights, falling back to local Whisper: {e}")
        model = ai_models.get_whisper_model(model_name)
        transcript = model.transcribe(video_path, fp16=False, language=language or None, verbose=False)
    
    transcript_segments = transcript.get("segments", [])

    keyword_segments = highlight_engine.detect_highlights_by_keywords(transcript_segments, category=category)
    audio_segments = highlight_engine.detect_highlights_by_audio(video_path, threshold_factor=audio_threshold)
    raw_candidates = keyword_segments + audio_segments

    with VideoFileClip(video_path) as video:
        planned_segments = highlight_engine.plan_highlight_segments(
            raw_candidates,
            video.duration,
            target_duration=target_duration,
            transcript_segments=transcript_segments,
        )
        planned_segments = highlight_engine.smooth_segments_to_transcript(
            planned_segments,
            transcript_segments,
            video.duration,
            target_duration=target_duration,
        )

    if not planned_segments:
        raise RuntimeError("AI could not find usable highlight segments in this video.")

    output_path = highlight_engine.extract_highlights(
        video_path,
        planned_segments,
        aspect_ratio=aspect_ratio,
        target_duration=None,
        audio_fade=0.22,
    )
    if not output_path or not os.path.exists(output_path):
        raise RuntimeError("Highlight rendering failed.")

    return {
        "output_path": output_path,
        "segments": planned_segments,
        "duration": sum(max(0.0, seg["end"] - seg["start"]) for seg in planned_segments),
        "transcript": transcript,
    }

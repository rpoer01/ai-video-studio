import datetime
import os
import re
from dataclasses import dataclass
from typing import Any

import numpy as np
from moviepy import VideoFileClip, afx, concatenate_videoclips

import ai_models
import highlight_engine

try:
    import cv2
except Exception:
    cv2 = None

try:
    from pythainlp.tokenize import word_tokenize as thai_word_tokenize
except Exception:
    thai_word_tokenize = None


OUTPUT_DIR = highlight_engine.OUTPUT_DIR


@dataclass
class AdvancedCandidate:
    source_index: int
    source_path: str
    start: float
    end: float
    score: float
    reason: str
    text: str
    audio_score: float
    visual_score: float
    semantic_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_index": self.source_index,
            "source_path": self.source_path,
            "start": self.start,
            "end": self.end,
            "score": self.score,
            "reason": self.reason,
            "text": self.text,
            "audio_score": self.audio_score,
            "visual_score": self.visual_score,
            "semantic_score": self.semantic_score,
        }


def _has_thai(text: str) -> bool:
    return any("\u0e00" <= char <= "\u0e7f" for char in str(text or ""))


def _tokens(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", str(text or "").strip().lower())
    if not text:
        return []
    if _has_thai(text) and thai_word_tokenize:
        try:
            return [token.strip().lower() for token in thai_word_tokenize(text.replace(" ", ""), engine="newmm") if token.strip()]
        except Exception:
            pass
    if _has_thai(text):
        return re.findall(r"[\u0e00-\u0e7f]{2,}|[A-Za-z0-9]+", text)
    return re.findall(r"[A-Za-z0-9']+", text)


def _semantic_score(text: str, prompt_terms: set[str]) -> tuple[float, list[str]]:
    if not prompt_terms:
        return 0.0, []
    text_compact = str(text or "").lower().replace(" ", "")
    hits = []
    for term in prompt_terms:
        if term and (term in text_compact or term in str(text or "").lower()):
            hits.append(term)
    score = min(1.0, len(hits) / max(1.0, min(4, len(prompt_terms))))
    return score, hits[:5]


def _audio_profile(video: VideoFileClip, fps: float = 2.0) -> dict[str, Any]:
    if video.audio is None or video.duration <= 0:
        return {"times": np.array([]), "scores": np.array([])}
    times = np.arange(0, video.duration, 1 / fps)
    volumes = []
    for t in times:
        try:
            end_t = min(float(t + 1 / fps), float(video.duration))
            chunk = video.audio.subclipped(float(t), end_t).to_soundarray(fps=22050)
            volumes.append(float(np.sqrt(np.mean(chunk**2))) if chunk.size else 0.0)
        except Exception:
            volumes.append(0.0)
    values = np.array(volumes, dtype=float)
    if values.size == 0 or float(np.max(values)) <= 0:
        return {"times": times, "scores": np.zeros_like(times)}
    baseline = float(np.percentile(values, 55))
    peak = float(np.percentile(values, 94)) or float(np.max(values))
    scores = np.clip((values - baseline) / max(0.0001, peak - baseline), 0.0, 1.0)
    return {"times": times, "scores": scores}


def _score_window(profile: dict[str, Any], start: float, end: float) -> float:
    times = profile.get("times", np.array([]))
    scores = profile.get("scores", np.array([]))
    if len(times) == 0:
        return 0.0
    mask = (times >= start) & (times <= end)
    if not np.any(mask):
        return 0.0
    return float(np.mean(scores[mask]))


def _visual_profile(video_path: str, duration: float, sample_fps: float = 1.0) -> dict[str, Any]:
    times = np.arange(0, max(0.0, duration), 1 / sample_fps)
    if len(times) == 0:
        return {"times": times, "scores": np.array([])}

    scores = []
    previous_gray = None
    with VideoFileClip(video_path) as video:
        for t in times:
            try:
                frame = video.get_frame(float(min(t, max(0.0, duration - 0.05))))
                if cv2 is not None:
                    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                    gray = cv2.resize(gray, (160, 90))
                else:
                    gray = np.mean(frame[:: max(1, frame.shape[0] // 90), :: max(1, frame.shape[1] // 160), :], axis=2)
                brightness = float(np.mean(gray)) / 255.0
                contrast = min(1.0, float(np.std(gray)) / 64.0)
                motion = 0.0
                if previous_gray is not None:
                    motion = min(1.0, float(np.mean(np.abs(gray.astype(float) - previous_gray.astype(float)))) / 32.0)
                previous_gray = gray
                scores.append(min(1.0, motion * 0.58 + contrast * 0.30 + brightness * 0.12))
            except Exception:
                scores.append(0.0)
    return {"times": times, "scores": np.array(scores, dtype=float)}


def _build_candidates(
    source_index: int,
    video_path: str,
    transcript_segments: list[dict[str, Any]],
    audio_profile: dict[str, Any],
    visual_profile: dict[str, Any],
    prompt_terms: set[str],
    duration: float,
) -> list[AdvancedCandidate]:
    candidates: list[AdvancedCandidate] = []
    for seg in transcript_segments:
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        start = max(0.0, float(seg.get("start", 0.0)) - 0.6)
        end = min(duration, float(seg.get("end", start + 1.5)) + 0.8)
        if end - start < 1.0:
            end = min(duration, start + 1.0)
        audio_score = _score_window(audio_profile, start, end)
        visual_score = _score_window(visual_profile, start, end)
        semantic, hits = _semantic_score(text, prompt_terms)
        intro_bias = max(0.0, 1.0 - (start / max(1.0, duration * 0.22))) * 0.12
        score = semantic * 3.0 + audio_score * 1.6 + visual_score * 1.25 + intro_bias
        reason_parts = []
        if hits:
            reason_parts.append("brief: " + ", ".join(hits))
        if audio_score > 0.45:
            reason_parts.append("audio lift")
        if visual_score > 0.42:
            reason_parts.append("visual motion")
        candidates.append(
            AdvancedCandidate(
                source_index=source_index,
                source_path=video_path,
                start=start,
                end=end,
                score=score,
                reason=" + ".join(reason_parts) or "balanced speech/audio/visual",
                text=text,
                audio_score=audio_score,
                visual_score=visual_score,
                semantic_score=semantic,
            )
        )
    return candidates


def _select_candidates(candidates: list[AdvancedCandidate], target_duration: float) -> list[AdvancedCandidate]:
    selected: list[AdvancedCandidate] = []
    total = 0.0
    for candidate in sorted(candidates, key=lambda item: item.score, reverse=True):
        if total >= target_duration - 0.2:
            break
        if any(
            candidate.source_path == chosen.source_path
            and candidate.start < chosen.end
            and chosen.start < candidate.end
            for chosen in selected
        ):
            continue
        remaining = target_duration - total
        if remaining < 1.0:
            break
        if candidate.end - candidate.start > remaining:
            candidate = AdvancedCandidate(
                **{**candidate.to_dict(), "end": candidate.start + remaining}
            )
        selected.append(candidate)
        total += max(0.0, candidate.end - candidate.start)
    selected.sort(key=lambda item: (item.source_index, item.start))
    return selected


def _crop_clip(clip, aspect_ratio: str):
    if aspect_ratio != "9:16":
        return clip
    target_ratio = 9 / 16
    current_ratio = clip.w / clip.h
    if current_ratio > target_ratio:
        new_w = clip.h * target_ratio
        clip = clip.cropped(x_center=clip.w / 2, width=new_w) if hasattr(clip, "cropped") else clip.crop(x1=(clip.w - new_w) / 2, width=new_w)
    else:
        new_h = clip.w / target_ratio
        clip = clip.cropped(y_center=clip.h / 2, height=new_h) if hasattr(clip, "cropped") else clip.crop(y1=(clip.h - new_h) / 2, height=new_h)
    return clip.resized(height=1920) if hasattr(clip, "resized") else clip.resize(height=1920)


def _render_selected(selected: list[AdvancedCandidate], aspect_ratio: str) -> str:
    clips = []
    open_videos = []
    try:
        for candidate in selected:
            video = VideoFileClip(candidate.source_path)
            open_videos.append(video)
            clip = video.subclipped(candidate.start, candidate.end) if hasattr(video, "subclipped") else video.subclip(candidate.start, candidate.end)
            clip = _crop_clip(clip, aspect_ratio)
            if clip.audio is not None:
                fade = min(0.18, max(0.04, clip.duration / 5.0))
                clip = clip.with_effects([afx.AudioFadeIn(fade), afx.AudioFadeOut(fade)])
            clips.append(clip)
        if not clips:
            raise RuntimeError("Advanced analyzer did not select any usable clips.")
        final_clip = concatenate_videoclips(clips, method="compose")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(OUTPUT_DIR, f"advanced_mix_{timestamp}.mp4")
        final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac", fps=clips[0].fps)
        final_clip.close()
        return output_path
    finally:
        for clip in clips:
            try:
                clip.close()
            except Exception:
                pass
        for video in open_videos:
            try:
                video.close()
            except Exception:
                pass


def analyze_and_render(
    video_paths: list[str],
    brief: str,
    model_name: str = "base",
    language: str | None = None,
    target_duration: float = 45.0,
    aspect_ratio: str = "9:16",
) -> dict[str, Any]:
    if not video_paths:
        raise ValueError("Add at least one video for Advanced Mode.")

    prompt_terms = set(_tokens(brief))
    model = ai_models.get_whisper_model(model_name)
    all_candidates: list[AdvancedCandidate] = []
    sources = []

    for index, video_path in enumerate(video_paths):
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file was not found: {video_path}")
        with VideoFileClip(video_path) as video:
            duration = float(video.duration)
            audio_profile = _audio_profile(video)
        
        print(f"[*] Analyzing source {index+1} with AssemblyAI...")
        try:
            transcript = ai_models.transcribe_with_assemblyai(video_path, language=language)
        except Exception as e:
            print(f"[!] AssemblyAI failed for source {index+1}, falling back to local Whisper: {e}")
            model = ai_models.get_whisper_model(model_name)
            transcript = model.transcribe(video_path, fp16=False, language=language or None, verbose=False)
            
        transcript_segments = transcript.get("segments", [])
        visual_profile = _visual_profile(video_path, duration)
        candidates = _build_candidates(
            index,
            video_path,
            transcript_segments,
            audio_profile,
            visual_profile,
            prompt_terms,
            duration,
        )
        all_candidates.extend(candidates)
        sources.append({"path": video_path, "duration": duration, "candidates": len(candidates)})

    if not all_candidates:
        raise RuntimeError("Advanced analyzer could not build candidates from the supplied videos.")
    selected = _select_candidates(all_candidates, max(5.0, float(target_duration)))
    output_path = _render_selected(selected, aspect_ratio)
    return {
        "output_path": output_path,
        "selected": [candidate.to_dict() for candidate in selected],
        "sources": sources,
        "brief_terms": sorted(prompt_terms),
        "duration": sum(max(0.0, item.end - item.start) for item in selected),
    }

import os
import re
from typing import Iterable

import numpy as np
import yt_dlp
from moviepy import VideoFileClip, afx, concatenate_videoclips

try:
    from pythainlp.tokenize import word_tokenize as thai_word_tokenize
except Exception:
    thai_word_tokenize = None

# Create shared output directory
OUTPUT_DIR = "outputs"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

CATEGORIES = {
    "General": ["สวย", "สุดยอด", "ดีมาก", "ว้าว", "โอ้โห"],
    "Gaming": ["แตก", "ยับ", "คม", "โหด", "เรียบร้อย", "เอาว่ะ", "มหาเทพ", "จังหวะ", "เชรด", "คิล", "Triple Kill", "Ace"],
    "Vlog/Review": ["น่าสนใจ", "แนะนำ", "ห้ามพลาด", "ดีมาก", "ว้าว", "ราคา", "คุ้ม", "ลองดู"],
    "Business/News": ["สำคัญ", "สรุป", "วิเคราะห์", "ประเด็น", "เติบโต", "เป้าหมาย", "กำไร", "ขาดทุน"]
}

HIGH_INTENT_KEYWORDS = [
    "ห้ามพลาด",
    "โคตร",
    "เดือด",
    "พีค",
    "ช็อก",
    "ตกใจ",
    "เหลือเชื่อ",
    "น่าสนใจ",
    "สำคัญมาก",
    "ไฮไลต์",
]


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _keyword_pool(category: str) -> list[str]:
    if category == "Auto":
        keywords: list[str] = []
        for values in CATEGORIES.values():
            keywords.extend(values)
        keywords.extend(HIGH_INTENT_KEYWORDS)
        return list(dict.fromkeys(keywords))
    return list(dict.fromkeys(CATEGORIES.get(category, CATEGORIES["General"]) + HIGH_INTENT_KEYWORDS))


def _keyword_hits(text: str, keywords: list[str]) -> list[str]:
    normalized = _normalize_text(text)
    compact = normalized.replace(" ", "")
    tokens = []
    if thai_word_tokenize and any("\u0e00" <= char <= "\u0e7f" for char in normalized):
        try:
            tokens = [token.strip().lower() for token in thai_word_tokenize(normalized, engine="newmm") if token.strip()]
        except Exception:
            tokens = []

    hits = []
    for keyword in keywords:
        key = _normalize_text(keyword)
        if not key:
            continue
        compact_key = key.replace(" ", "")
        if key in normalized or compact_key in compact or key in tokens:
            hits.append(keyword)
    return list(dict.fromkeys(hits))

def download_video(url, output_dir="downloads"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

def _duration(seg: dict) -> float:
    return max(0.0, float(seg["end"]) - float(seg["start"]))


def _clean_segment(seg: dict, video_duration: float | None = None) -> dict | None:
    start = max(0.0, float(seg.get("start", 0.0)))
    end = max(start, float(seg.get("end", start)))
    if video_duration is not None:
        end = min(float(video_duration), end)
    if end - start <= 0.05:
        return None
    cleaned = dict(seg)
    cleaned["start"] = start
    cleaned["end"] = end
    cleaned["score"] = float(cleaned.get("score", 1.0))
    cleaned["reason"] = str(cleaned.get("reason", "Candidate"))
    return cleaned


def _overlaps(a: dict, b: dict, gap: float = 0.15) -> bool:
    return a["start"] < b["end"] - gap and b["start"] < a["end"] - gap


def _too_close(a: dict, b: dict, min_gap: float) -> bool:
    return abs(a["start"] - b["start"]) < min_gap or abs(a["end"] - b["end"]) < min_gap


def _format_reasons(reasons: Iterable[str], limit: int = 4) -> str:
    unique = []
    for reason in reasons:
        if reason and reason not in unique:
            unique.append(reason)
    if len(unique) > limit:
        unique = unique[:limit] + ["more"]
    return " + ".join(unique) or "Highlight"


def detect_highlights_by_keywords(segments, category="General", padding=2.0):
    highlights = []
    keywords = _keyword_pool(category)
    for seg in segments:
        text = seg['text']
        hits = _keyword_hits(text, keywords)
        if hits:
            start = max(0, seg['start'] - padding)
            end = seg['end'] + padding
            score_bonus = min(4.0, len(hits) * 0.75)
            highlights.append({
                'start': start,
                'end': end,
                'score': 4.0 + score_bonus,
                'reason': f"Keyword ({category}: {', '.join(hits[:4])}): {text.strip()}"
            })
    return highlights


def detect_highlights_by_audio(video_path, threshold_factor=2.0, min_duration=1.0):
    video = VideoFileClip(video_path)
    audio = video.audio
    if audio is None:
        video.close()
        return []
    
    duration = video.duration
    fps = 2  # Sample every 0.5 seconds
    
    volumes = []
    times = np.arange(0, duration, 1/fps)
    
    for t in times:
        try:
            end_t = min(t + 1/fps, duration)
            if t >= duration: break
            # Compatibility check
            if hasattr(audio, "subclipped"):
                chunk = audio.subclipped(t, end_t).to_soundarray(fps=44100)
            else:
                chunk = audio.subclip(t, end_t).to_soundarray(fps=44100)
        except Exception:
            break
        
        if chunk.size == 0:
            volumes.append(0)
            continue
        volume = np.sqrt(np.mean(chunk**2))
        volumes.append(volume)
    
    if not volumes:
        video.close()
        return []

    avg_volume = float(np.mean(volumes))
    percentile_threshold = float(np.percentile(volumes, 82))
    threshold = max(avg_volume * threshold_factor, percentile_threshold)
    if threshold <= 0:
        video.close()
        return []
    
    highlights = []
    current_start = None
    
    for i, vol in enumerate(volumes):
        if vol > threshold:
            if current_start is None:
                current_start = times[i]
        else:
            if current_start is not None:
                end = times[i]
                if end - current_start >= min_duration:
                    peak = max(volumes[max(0, i - int((end - current_start) * fps)):i] or [threshold])
                    highlights.append({
                        'start': max(0, current_start - 1.5),
                        'end': min(duration, end + 1.5),
                        'score': 2.0 + float(peak / threshold),
                        'reason': "Audio Peak"
                    })
                current_start = None
                
    if current_start is not None:
        highlights.append({'start': max(0, current_start - 1.5), 'end': duration, 'score': 2.5, 'reason': "Audio Peak"})
        
    video.close()
    return highlights


def build_transcript_candidates(segments, target_window=12.0, padding=1.0):
    """Build speech-based backup candidates so short keyword/audio hits can still reach the requested length."""
    candidates = []
    current = None
    reasons = []
    word_count = 0

    for seg in segments or []:
        text = str(seg.get("text", "")).strip()
        if not text:
            continue

        start = max(0.0, float(seg["start"]) - padding)
        end = float(seg["end"]) + padding
        if current is None:
            current = {"start": start, "end": end}
            reasons = [f"Speech: {text[:80]}"]
            word_count = len(text.split())
            continue

        gap = start - current["end"]
        current_len = current["end"] - current["start"]
        should_close = current_len >= target_window or gap > 2.5
        if should_close:
            duration_score = min(2.0, current_len / max(1.0, target_window))
            candidates.append({
                "start": current["start"],
                "end": current["end"],
                "score": 1.0 + duration_score + min(1.0, word_count / 35.0),
                "reason": _format_reasons(reasons, limit=2),
            })
            current = {"start": start, "end": end}
            reasons = [f"Speech: {text[:80]}"]
            word_count = len(text.split())
        else:
            current["end"] = max(current["end"], end)
            reasons.append(f"Speech: {text[:80]}")
            word_count += len(text.split())

    if current is not None:
        current_len = current["end"] - current["start"]
        candidates.append({
            "start": current["start"],
            "end": current["end"],
            "score": 1.0 + min(2.0, current_len / max(1.0, target_window)) + min(1.0, word_count / 35.0),
            "reason": _format_reasons(reasons, limit=2),
        })

    return candidates


def merge_segments(segments, max_gap=2.0, max_total_duration=None):
    if not segments:
        return []
    
    # Sort by start time
    segments.sort(key=lambda x: x['start'])
    
    merged = []
    current = segments[0].copy()
    
    for i in range(1, len(segments)):
        next_seg = segments[i]
        if next_seg['start'] <= current['end'] + max_gap:
            current['end'] = max(current['end'], next_seg['end'])
            current['score'] = max(float(current.get('score', 1.0)), float(next_seg.get('score', 1.0)))
            current['reason'] = _format_reasons([current.get('reason', ''), next_seg.get('reason', '')])
        else:
            merged.append(current)
            current = next_seg.copy()
    merged.append(current)
    
    # Optional: Limit total duration by taking the top X segments
    if max_total_duration:
        total_time = 0
        limited = []
        for seg in merged:
            dur = seg['end'] - seg['start']
            if total_time + dur <= max_total_duration:
                limited.append(seg)
                total_time += dur
            else:
                # Add partial segment if needed to reach exactly max_duration
                remaining = max_total_duration - total_time
                if remaining > 1.0:
                    seg['end'] = seg['start'] + remaining
                    limited.append(seg)
                break
        return limited
        
    return merged


def _limit_segments_to_duration(segments, max_total_duration):
    if not max_total_duration:
        return segments

    total_time = 0.0
    limited = []
    for source in segments:
        seg = source.copy()
        dur = _duration(seg)
        remaining = float(max_total_duration) - total_time
        if remaining <= 0:
            break
        if dur <= remaining:
            limited.append(seg)
            total_time += dur
        elif remaining >= 1.0:
            seg["end"] = seg["start"] + remaining
            limited.append(seg)
            break
    return limited


def smooth_segments_to_transcript(
    segments,
    transcript_segments,
    video_duration,
    target_duration=None,
    pre_roll=0.2,
    post_roll=0.35,
    max_extension=1.75,
):
    """Move cut points toward speech boundaries so voices do not jump mid-word."""
    if not segments or not transcript_segments:
        return segments

    video_duration = float(video_duration)
    smoothed = []
    for source in segments:
        seg = source.copy()
        overlapping = [
            t for t in transcript_segments
            if float(t.get("end", 0)) > seg["start"] and float(t.get("start", 0)) < seg["end"]
        ]
        if overlapping:
            speech_start = max(0.0, float(overlapping[0]["start"]) - pre_roll)
            speech_end = min(video_duration, float(overlapping[-1]["end"]) + post_roll)
            seg["start"] = max(0.0, max(seg["start"] - max_extension, min(seg["start"], speech_start)))
            seg["end"] = min(video_duration, min(seg["end"] + max_extension, max(seg["end"], speech_end)))
            seg["reason"] = _format_reasons([seg.get("reason", ""), "Speech boundary"])
        smoothed.append(seg)

    smoothed = merge_segments(sorted(smoothed, key=lambda s: s["start"]), max_gap=0.35)

    if target_duration:
        total = sum(_duration(seg) for seg in smoothed)
        target = float(target_duration)
        if total > target + 2.0:
            over = total - (target + 1.0)
            for seg in reversed(smoothed):
                if over <= 0:
                    break
                removable = max(0.0, _duration(seg) - 4.0)
                trim = min(removable, over)
                if trim:
                    seg["end"] -= trim
                    over -= trim

    return [seg for seg in smoothed if _duration(seg) >= 0.5]


def _expand_segment(seg, video_duration, desired_duration):
    desired_duration = min(float(desired_duration), float(video_duration))
    current_duration = _duration(seg)
    if current_duration >= desired_duration:
        return seg

    extra = desired_duration - current_duration
    before = min(seg["start"], extra / 2)
    after = min(video_duration - seg["end"], extra - before)
    before = min(seg["start"], extra - after)

    expanded = seg.copy()
    expanded["start"] = max(0.0, seg["start"] - before)
    expanded["end"] = min(video_duration, seg["end"] + after)
    return expanded


def plan_highlight_segments(
    segments,
    video_duration,
    target_duration=None,
    transcript_segments=None,
    context_padding=2.5,
    min_segment_duration=6.0,
    max_segment_duration=18.0,
    min_scene_gap=4.0,
):
    """Choose strong moments and make the total duration close to the user's target."""
    video_duration = float(video_duration)
    if video_duration <= 0:
        return []

    target = min(float(target_duration or video_duration), video_duration)
    candidates = []
    for seg in segments or []:
        cleaned = _clean_segment(seg, video_duration)
        if cleaned is None:
            continue
        cleaned["start"] = max(0.0, cleaned["start"] - context_padding)
        cleaned["end"] = min(video_duration, cleaned["end"] + context_padding)
        wanted = min(max_segment_duration, max(min_segment_duration, _duration(cleaned)))
        candidates.append(_expand_segment(cleaned, video_duration, wanted))

    speech_candidates = build_transcript_candidates(
        transcript_segments or [],
        target_window=max(8.0, min(14.0, target / 4.0)),
        padding=1.0,
    )
    for seg in speech_candidates:
        cleaned = _clean_segment(seg, video_duration)
        if cleaned is not None:
            candidates.append(_expand_segment(cleaned, video_duration, min(max_segment_duration, max(min_segment_duration, _duration(cleaned)))))

    if not candidates:
        step = max(5.0, min(max_segment_duration, target))
        t = 0.0
        while t < video_duration and len(candidates) < 12:
            candidates.append({"start": t, "end": min(video_duration, t + step), "score": 0.2, "reason": "Fallback slice"})
            t += step * 1.75

    candidates.sort(key=lambda s: (float(s.get("score", 1.0)), _duration(s)), reverse=True)

    selected = []
    total = 0.0
    for allow_close in (False, True):
        for candidate in candidates:
            if total >= target - 0.25:
                break
            if any(_overlaps(candidate, chosen) for chosen in selected):
                continue
            if not allow_close and any(_too_close(candidate, chosen, min_scene_gap) for chosen in selected):
                continue
            remaining = target - total
            seg = candidate.copy()
            if _duration(seg) > remaining and remaining >= 4.0:
                seg["end"] = seg["start"] + remaining
            selected.append(seg)
            total += _duration(seg)
        if total >= target - 0.25:
            break

    if selected and total < target - 0.25:
        selected.sort(key=lambda s: s["start"])
        remaining = target - total
        while remaining > 0.25:
            changed = False
            for i, seg in enumerate(selected):
                if remaining <= 0.25:
                    break
                prev_end = selected[i - 1]["end"] if i > 0 else 0.0
                next_start = selected[i + 1]["start"] if i + 1 < len(selected) else video_duration
                before_room = max(0.0, seg["start"] - prev_end - 0.15)
                after_room = max(0.0, next_start - seg["end"] - 0.15)
                grow_before = min(before_room, remaining / 2.0, 2.0)
                grow_after = min(after_room, remaining - grow_before, 2.0)
                if grow_before or grow_after:
                    seg["start"] -= grow_before
                    seg["end"] += grow_after
                    remaining -= grow_before + grow_after
                    changed = True
            if not changed:
                break

    selected.sort(key=lambda s: s["start"])
    return _limit_segments_to_duration(selected, target)


def _apply_audio_edge_smoothing(clip, fade_duration=0.18):
    fade = min(float(fade_duration), max(0.03, clip.duration / 4.0))
    if fade <= 0 or clip.audio is None:
        return clip
    return clip.with_effects([afx.AudioFadeIn(fade), afx.AudioFadeOut(fade)])


def extract_highlights(video_path, segments, aspect_ratio="16:9", max_duration=None, target_duration=None, audio_fade=0.18):
    if not segments:
        return None
    
    video = VideoFileClip(video_path)
    target = target_duration if target_duration is not None else max_duration
    if target:
        segments = plan_highlight_segments(segments, video.duration, target_duration=target)
    else:
        segments = merge_segments(segments)
    clips = []
    
    for seg in segments:
        start = max(0, seg['start'])
        end = min(video.duration, seg['end'])
        
        try:
            if hasattr(video, "subclipped"):
                clip = video.subclipped(start, end)
            else:
                clip = video.subclip(start, end)
                
            # PRO CROP: 9:16 for TikTok
            if aspect_ratio == "9:16":
                target_ratio = 9/16
                current_ratio = clip.w / clip.h
                
                if current_ratio > target_ratio:
                    # Clip is too wide, crop sides
                    new_w = clip.h * target_ratio
                    # Using explicit cropping for v2 and v1 compatibility
                    if hasattr(clip, "cropped"):
                        clip = clip.cropped(x_center=clip.w/2, width=new_w)
                    else:
                        x1 = (clip.w - new_w) / 2
                        clip = clip.crop(x1=x1, width=new_w)
                else:
                    # Clip is too tall, crop top/bottom
                    new_h = clip.w / target_ratio
                    if hasattr(clip, "cropped"):
                        clip = clip.cropped(y_center=clip.h/2, height=new_h)
                    else:
                        y1 = (clip.h - new_h) / 2
                        clip = clip.crop(y1=y1, height=new_h)
                
                # Rescale to 1080x1920 for "Real" TikTok quality
                if hasattr(clip, "resized"):
                    clip = clip.resized(height=1920)
                else:
                    clip = clip.resize(height=1920)
            
            clips.append(_apply_audio_edge_smoothing(clip, audio_fade))
        except Exception as e:
            print(f"[!] Error cutting segment: {e}")
            continue
    
    if not clips:
        video.close()
        return None
        
    final_clip = concatenate_videoclips(clips, method="compose")
    
    # Save to outputs folder
    base_name = os.path.basename(video_path)
    suffix = "_tiktok" if aspect_ratio == "9:16" else "_highlights"
    output_filename = os.path.splitext(base_name)[0] + f"{suffix}.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
        
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac", fps=video.fps)
    
    # Explicit cleanup
    final_clip.close()
    video.close()
    for c in clips: c.close()
    
    return output_path

if __name__ == "__main__":
    pass

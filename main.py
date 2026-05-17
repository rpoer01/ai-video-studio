import datetime
import glob
import os
import shutil
import threading
import time
import traceback
import uuid
import ai_models
import advanced_video_analyzer
import highlight_engine
import highlight_pipeline
import utils
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
from typing import Any
from flask import Flask, abort, render_template_string, request, jsonify, send_file, url_for
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from moviepy import CompositeVideoClip, ImageClip, VideoFileClip, vfx

# Configure paths and fonts
font_paths = utils.download_required_fonts()
OUTPUT_DIR = highlight_engine.OUTPUT_DIR

def configure_imagemagick() -> None:
    common_paths = [
        r"C:\Program Files\ImageMagick-*\magick.exe",
        r"C:\Program Files (x86)\ImageMagick-*\magick.exe",
    ]
    for pattern in common_paths:
        matches = glob.glob(pattern)
        if matches:
            os.environ["IMAGEMAGICK_BINARY"] = matches[0]
            return

def configure_ffmpeg() -> None:
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_dir = os.path.dirname(ffmpeg_exe)
    local_ffmpeg = os.path.join(ffmpeg_dir, "ffmpeg.exe")
    if not os.path.exists(local_ffmpeg):
        try:
            shutil.copy(ffmpeg_exe, local_ffmpeg)
        except Exception:
            pass
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

configure_imagemagick()
configure_ffmpeg()

app = Flask(__name__)

JOB_EXECUTOR = ThreadPoolExecutor(max_workers=1)
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()
MAX_JOBS = 30


def _public_job(job: dict[str, Any]) -> dict[str, Any]:
    public = {k: v for k, v in job.items() if k != "traceback"}
    return public


def _set_job(job_id: str, **updates: Any) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        job.update(updates)
        job["updated_at"] = time.time()


def _trim_jobs() -> None:
    with JOBS_LOCK:
        if len(JOBS) <= MAX_JOBS:
            return
        removable = sorted(
            JOBS.items(),
            key=lambda item: item[1].get("updated_at", item[1].get("created_at", 0)),
        )
        for job_id, job in removable[: len(JOBS) - MAX_JOBS]:
            if job.get("status") in {"done", "error"}:
                JOBS.pop(job_id, None)


def _parse_process_form(form) -> dict[str, Any]:
    video_input = form.get("video_input", "").strip().strip('"').strip("'")
    if not video_input:
        raise ValueError("Video input is required.")

    try:
        max_duration = float(form.get("max_duration", "60"))
    except ValueError as exc:
        raise ValueError("Clip duration must be a number.") from exc
    max_duration = max(5.0, min(300.0, max_duration))

    return {
        "video_input": video_input,
        "source_type": form.get("source_type", "url"),
        "mode": form.get("mode", "subtitles_only"),
        "model_name": form.get("model_name", "base"),
        "language": form.get("language", ""),
        "style_name": form.get("style_name", "Vibrant TikTok"),
        "caption_font_name": form.get("caption_font_name", "Kanit Bold"),
        "animation_name": form.get("animation_name", "Smooth Pop"),
        "aspect_ratio": form.get("aspect_ratio", "9:16"),
        "translate": form.get("translate") == "on",
        "max_duration": max_duration,
        "pos_x": float(form.get("pos_x", "0.5")),
        "pos_y": float(form.get("pos_y", "0.75")),
    }


def _parse_advanced_form(form) -> dict[str, Any]:
    raw_paths = form.get("video_paths", "")
    video_paths = [
        line.strip().strip('"').strip("'")
        for line in raw_paths.replace(";", "\n").splitlines()
        if line.strip()
    ]
    if not video_paths:
        raise ValueError("Add at least one video path.")
    try:
        target_duration = float(form.get("target_duration", "45"))
    except ValueError as exc:
        raise ValueError("Target duration must be a number.") from exc

    return {
        "video_paths": video_paths,
        "brief": form.get("brief", "").strip(),
        "model_name": form.get("model_name", "base"),
        "language": form.get("language", ""),
        "target_duration": max(5.0, min(300.0, target_duration)),
        "aspect_ratio": form.get("aspect_ratio", "9:16"),
        "add_subtitles": form.get("add_subtitles") == "on",
        "style_name": form.get("style_name", "Vibrant TikTok"),
        "caption_font_name": form.get("caption_font_name", "Kanit Bold"),
        "animation_name": form.get("animation_name", "Smooth Pop"),
    }


def _produce_video(params: dict[str, Any], job_id: str | None = None) -> dict[str, str]:
    video_path = params["video_input"]
    if params["source_type"] == "url" and video_path.startswith("http"):
        if job_id:
            _set_job(job_id, message="Downloading source video...")
        video_path = highlight_engine.download_video(video_path)

    if not os.path.exists(video_path):
        raise RuntimeError(f"Video file was not found: {video_path}")

    if params.get("mode") == "highlights":
        if job_id:
            _set_job(job_id, message="Finding and cutting highlight segments...")
        cut_result = highlight_pipeline.cut_highlight_video(
            video_path=video_path,
            model_name=params["model_name"],
            language=params["language"] if params["language"] else None,
            aspect_ratio=params["aspect_ratio"],
            target_duration=params["max_duration"],
            category="Auto",
            audio_threshold=2.5,
        )
        master_path = cut_result["output_path"]
        print(f"[*] Planned highlight length: {cut_result['duration']:.2f}s across {len(cut_result['segments'])} segments")
    else:
        # Subtitles Only mode - use original video
        master_path = video_path
        if job_id:
            _set_job(job_id, message="Processing original video (Full Duration)...")

    if job_id:
        _set_job(job_id, message="Rendering animated captions...")
    result = render_pro_video(
        master_path,
        params["model_name"],
        params["style_name"],
        params["pos_x"],
        params["pos_y"],
        params["language"],
        params["translate"],
        caption_font_name=params["caption_font_name"],
        animation_name=params["animation_name"],
        output_suffix="_final",
    )
    if job_id:
        _set_job(job_id, message="Final video ready. Updating preview...")
    return result


def _produce_advanced_video(params: dict[str, Any], job_id: str | None = None) -> dict[str, Any]:
    if job_id:
        _set_job(job_id, message="Analyzing speech, audio energy, and visual motion...")
    analysis = advanced_video_analyzer.analyze_and_render(
        video_paths=params["video_paths"],
        brief=params["brief"],
        model_name=params["model_name"],
        language=params["language"] if params["language"] else None,
        target_duration=params["target_duration"],
        aspect_ratio=params["aspect_ratio"],
    )
    output_path = analysis["output_path"]

    if params["add_subtitles"]:
        if job_id:
            _set_job(job_id, message="Adding automatic subtitles to advanced cut...")
        result = render_pro_video(
            output_path,
            params["model_name"],
            params["style_name"],
            0.5,
            0.66,
            params["language"],
            False,
            caption_font_name=params["caption_font_name"],
            animation_name=params["animation_name"],
            output_suffix="_subtitled",
        )
    else:
        output_basename = os.path.basename(output_path)
        result = {
            "output_video": os.path.abspath(output_path),
            "output_url": f"/outputs/{quote(output_basename)}",
        }
    result["analysis"] = analysis
    return result


def _run_job(job_id: str, params: dict[str, Any]) -> None:
    try:
        _set_job(job_id, status="running", message="Starting AI Studio production...")
        result = _produce_video(params, job_id=job_id)
        _set_job(job_id, status="done", message="Completed. Preview is ready.", result=result)
    except Exception as exc:
        traceback.print_exc()
        _set_job(job_id, status="error", message=str(exc), traceback=traceback.format_exc())


def _run_advanced_job(job_id: str, params: dict[str, Any]) -> None:
    try:
        _set_job(job_id, status="running", message="Starting Advanced video analysis...")
        result = _produce_advanced_video(params, job_id=job_id)
        _set_job(job_id, status="done", message="Advanced edit is ready.", result=result)
    except Exception as exc:
        traceback.print_exc()
        _set_job(job_id, status="error", message=str(exc), traceback=traceback.format_exc())


def _start_job(params: dict[str, Any]) -> str:
    _trim_jobs()
    job_id = uuid.uuid4().hex
    now = time.time()
    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "status": "queued",
            "message": "Queued.",
            "result": None,
            "created_at": now,
            "updated_at": now,
        }
    JOB_EXECUTOR.submit(_run_job, job_id, params)
    return job_id


def _start_advanced_job(params: dict[str, Any]) -> str:
    _trim_jobs()
    job_id = uuid.uuid4().hex
    now = time.time()
    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "status": "queued",
            "message": "Queued.",
            "result": None,
            "created_at": now,
            "updated_at": now,
        }
    JOB_EXECUTOR.submit(_run_advanced_job, job_id, params)
    return job_id


def _latest_output_result() -> dict[str, str] | None:
    pattern = os.path.join(OUTPUT_DIR, "*_final.mp4")
    files = [path for path in glob.glob(pattern) if os.path.isfile(path)]
    if not files:
        return None
    latest = max(files, key=os.path.getmtime)
    output_basename = os.path.basename(latest)
    return {
        "output_video": os.path.abspath(latest),
        "output_url": f"/outputs/{quote(output_basename)}?v={int(os.path.getmtime(latest))}",
        "updated_at": os.path.getmtime(latest),
    }

# --- Ultra Pro Subtitle Engine v2 ---

SUBTITLE_STYLES = {
    "Vibrant TikTok": {
        "font": font_paths.get("Kanit-Bold", "Arial"),
        "font_size": 126,
        "color": "white",
        "highlight_color": "#25ff6a",
        "stroke_color": "black",
        "stroke_width": 8,
        "shadow": True
    },
    "Gamer Pro": {
        "font": font_paths.get("Prompt-Bold", "Arial"),
        "font_size": 132,
        "color": "white",
        "highlight_color": "#fff200",
        "stroke_color": "black",
        "stroke_width": 9,
        "shadow": True
    },
    "Minimal Dark": {
        "font": font_paths.get("Kanit-Bold", "Arial"),
        "font_size": 112,
        "color": "white",
        "highlight_color": "#25ff6a",
        "stroke_color": "black",
        "stroke_width": 6,
        "bg_color": "rgba(0,0,0,0.6)",
        "shadow": False
    }
}

CAPTION_FONTS = {
    "Kanit Bold": font_paths.get("Kanit-Bold", "Arial"),
    "Kanit Regular": font_paths.get("Kanit-Regular", "Arial"),
    "Prompt Bold": font_paths.get("Prompt-Bold", "Arial"),
    "Arial": "Arial",
}

CAPTION_ANIMATIONS = {
    "Smooth Pop": {"mode": "pop", "fade": 0.16, "slide": 14, "start_scale": 0.94, "end_scale": 0.985},
    "Slide Fade": {"mode": "slide", "fade": 0.18, "slide": 28, "start_scale": 1.0, "end_scale": 1.0},
    "Fade Only": {"mode": "fade", "fade": 0.14, "slide": 0, "start_scale": 1.0, "end_scale": 1.0},
    "None": {"mode": "none", "fade": 0.0, "slide": 0, "start_scale": 1.0, "end_scale": 1.0},
}


try:
    from pythainlp.tokenize import word_tokenize as thai_word_tokenize
except Exception:
    thai_word_tokenize = None

THAI_FALLBACK_WORDS = sorted(
    {
        "สวัสดี", "ครับ", "ค่ะ", "คะ", "นะ", "เลย", "มาก", "จริง", "จริงๆ", "นี่", "นี้",
        "คือ", "ที่", "และ", "หรือ", "แล้ว", "แต่", "เพราะ", "ก็", "ไม่", "ได้", "ให้",
        "มี", "เป็น", "ใน", "กับ", "ของ", "เรา", "เขา", "คน", "คลิป", "วิดีโอ",
        "ไฮไลต์", "สำคัญ", "สุดยอด", "เดือด", "พีค", "ห้ามพลาด", "น่าสนใจ",
        "วิเคราะห์", "สรุป", "ราคา", "คุ้ม", "ลองดู", "เป้าหมาย", "กำไร",
    },
    key=len,
    reverse=True,
)


def _has_thai(text: str) -> bool:
    return any("\u0e00" <= char <= "\u0e7f" for char in str(text or ""))


def _caption_join(words: list[str]) -> str:
    clean = [str(word).strip() for word in words if str(word).strip()]
    if not clean:
        return ""
    if any(_has_thai(word) for word in clean):
        return "".join(clean)
    return " ".join(clean)


def _caption_text_width(draw: ImageDraw.ImageDraw, words: list[str], font: ImageFont.FreeTypeFont) -> float:
    return draw.textlength(_caption_join(words), font=font)


def _caption_tokens_from_text(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", str(text or "").strip())
    if not text:
        return []
    if not _has_thai(text):
        return text.split()
    compact = text.replace(" ", "")
    if thai_word_tokenize:
        try:
            tokens = [token.strip() for token in thai_word_tokenize(compact, engine="newmm") if token.strip()]
            if tokens and not (len(tokens) == 1 and len(tokens[0]) > 12):
                return tokens
        except Exception:
            pass
    return _fallback_thai_tokens(compact)


def _fallback_thai_tokens(text: str, max_chars: int = 7) -> list[str]:
    tokens = []
    i = 0
    while i < len(text):
        if not ("\u0e00" <= text[i] <= "\u0e7f"):
            match = re.match(r"[A-Za-z0-9]+|[^\u0e00-\u0e7f]", text[i:])
            token = match.group(0) if match else text[i]
            tokens.append(token)
            i += len(token)
            continue

        matched = None
        for candidate in THAI_FALLBACK_WORDS:
            if text.startswith(candidate, i):
                matched = candidate
                break
        if matched:
            tokens.append(matched)
            i += len(matched)
            continue

        start = i
        i += 1
        while i < len(text) and i - start < max_chars:
            if any(text.startswith(candidate, i) for candidate in THAI_FALLBACK_WORDS):
                break
            i += 1
        tokens.append(text[start:i])
    return [token for token in tokens if token.strip()]


def _retime_caption_tokens(tokens: list[str], start: float, end: float) -> list[dict[str, Any]]:
    if not tokens:
        return []
    start = float(start)
    end = max(start + 0.08, float(end))
    total_units = sum(max(1, len(token)) for token in tokens)
    cursor = start
    retimed = []
    duration = end - start
    for index, token in enumerate(tokens):
        units = max(1, len(token))
        token_end = end if index == len(tokens) - 1 else cursor + duration * (units / total_units)
        retimed.append({"word": token, "start": cursor, "end": max(cursor + 0.08, token_end)})
        cursor = token_end
    return retimed


def _normalize_caption_words(words: list[dict[str, Any]], fallback_text: str = "") -> list[dict[str, Any]]:
    visible = [word for word in words if str(word.get("word", "")).strip()]
    source_text = fallback_text or _caption_join([word["word"] for word in visible])
    if not _has_thai(source_text):
        return [
            {**word, "word": str(word["word"]).strip().upper()}
            for word in visible
            if str(word.get("word", "")).strip()
        ]

    start = min((float(word.get("start", 0.0)) for word in visible), default=0.0)
    end = max((float(word.get("end", start + 0.1)) for word in visible), default=start + 0.1)
    tokens = _caption_tokens_from_text(source_text)
    return _retime_caption_tokens(tokens, start, end)


def _caption_phrase_groups(words: list[dict[str, Any]], max_tokens: int = 3) -> list[list[dict[str, Any]]]:
    normalized = _normalize_caption_words(words)
    groups = []
    current = []
    for word in normalized:
        current.append(word)
        if len(current) >= max_tokens:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def split_thai_text(text, max_len=15):
    """Simple Thai word splitting fallback as Thai has no spaces."""
    if not any(u'\u0e00' <= c <= u'\u0e7f' for c in text):
        return text.split()
    return _caption_tokens_from_text(text)

def _load_caption_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(font_path, size=size)
    except Exception:
        return ImageFont.truetype("arial.ttf", size=size)

def _text_bbox(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, stroke_width: int):
    return draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)

def _wrap_words_for_width(words: list[str], draw, font, max_width: int, stroke_width: int) -> list[list[str]]:
    lines: list[list[str]] = []
    current: list[str] = []
    for word in words:
        test = current + [word]
        bbox = _text_bbox(draw, _caption_join(test), font, stroke_width)
        if current and (bbox[2] - bbox[0]) > max_width:
            lines.append(current)
            current = [word]
        else:
            current = test
    if current:
        lines.append(current)
    return lines

def _layout_caption_words(words: list[str], style, video_w: int, video_h: int):
    max_w = int(video_w * 0.90)
    max_h = int(video_h * 0.20)
    min_size = max(54, int(video_w * 0.055))
    font_size = min(style["font_size"], int(video_w * 0.125))
    scratch = Image.new("RGBA", (16, 16))
    draw = ImageDraw.Draw(scratch)

    while font_size >= min_size:
        font = _load_caption_font(style["font"], font_size)
        stroke_width = max(4, int(font_size * 0.075))
        lines = _wrap_words_for_width(words, draw, font, max_w, stroke_width)
        line_metrics = []
        total_h = 0
        max_line_w = 0
        gap = max(4, int(font_size * 0.08))
        for line in lines:
            line_w = _caption_text_width(draw, line, font)
            bbox = _text_bbox(draw, _caption_join(line), font, stroke_width)
            line_h = bbox[3] - bbox[1]
            line_metrics.append((line_w, line_h))
            total_h += line_h
            max_line_w = max(max_line_w, int(line_w))
        total_h += gap * max(0, len(lines) - 1)
        if max_line_w <= max_w and total_h <= max_h:
            return font, stroke_width, lines, line_metrics, gap
        font_size -= 4

    font = _load_caption_font(style["font"], min_size)
    stroke_width = max(4, int(min_size * 0.075))
    lines = _wrap_words_for_width(words, draw, font, max_w, stroke_width)
    line_metrics = []
    gap = max(4, int(min_size * 0.08))
    for line in lines:
        line_w = _caption_text_width(draw, line, font)
        bbox = _text_bbox(draw, _caption_join(line), font, stroke_width)
        line_metrics.append((line_w, bbox[3] - bbox[1]))
    return font, stroke_width, lines, line_metrics, gap

def _render_karaoke_caption_image(words: list[str], active_index: int, style, video_w: int, video_h: int) -> Image.Image:
    font, stroke_width, lines, line_metrics, gap = _layout_caption_words(words, style, video_w, video_h)
    pad_x = max(34, int(video_w * 0.035))
    pad_y = max(22, int(video_h * 0.014))
    img_w = min(video_w, max(int(max(w for w, _ in line_metrics) + pad_x * 2), int(video_w * 0.45)))
    img_h = int(sum(h for _, h in line_metrics) + gap * max(0, len(lines) - 1) + pad_y * 2)
    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))

    shadow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    draw = ImageDraw.Draw(img)
    word_cursor = 0
    y = pad_y

    for line, (line_w, line_h) in zip(lines, line_metrics):
        full_line_text = _caption_join(line)
        line_bbox = _text_bbox(draw, full_line_text, font, stroke_width)
        draw_y = y - line_bbox[1]
        x_base = (img_w - line_w) / 2
        
        # 1. Render base line (all words in default color)
        # Using a slight blur on shadow for better legibility
        shadow_draw.text((x_base + 5, draw_y + 6), full_line_text, font=font, fill=(0, 0, 0, 210), stroke_width=stroke_width + 2, stroke_fill=(0, 0, 0, 230))
        draw.text((x_base, draw_y), full_line_text, font=font, fill=style["color"], stroke_width=stroke_width, stroke_fill=style["stroke_color"])

        # 2. Render the active word highlight exactly on top
        for line_index, word in enumerate(line):
            if word_cursor == active_index:
                # Calculate the exact x offset for the active word within the line
                prefix = _caption_join(line[:line_index])
                if prefix:
                    # In Thai, no space. In other languages, a space is added between tokens in _caption_join(line).
                    # We must match _caption_join's behavior exactly.
                    if not _has_thai(prefix[-1]) and not _has_thai(word[0]):
                        prefix += " "
                    word_x = x_base + draw.textlength(prefix, font=font)
                else:
                    word_x = x_base
                
                active_stroke = stroke_width + 1
                shadow_draw.text((word_x + 5, draw_y + 6), word, font=font, fill=(0, 0, 0, 210), stroke_width=active_stroke + 2, stroke_fill=(0, 0, 0, 230))
                draw.text((word_x, draw_y), word, font=font, fill=style["highlight_color"], stroke_width=active_stroke, stroke_fill=style["stroke_color"])
            
            word_cursor += 1
        y += line_h + gap

    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=2.5))
    return Image.alpha_composite(shadow_layer, img)

def _safe_caption_position_size(size, video_w, video_h, pos_x, pos_y):
    margin_x = max(18, int(video_w * 0.03))
    margin_y = max(24, int(video_h * 0.04))
    text_w, text_h = size
    x_pos = int(video_w * pos_x - text_w / 2)
    y_pos = int(video_h * pos_y - text_h / 2)
    x_pos = max(margin_x, min(x_pos, video_w - text_w - margin_x))
    y_pos = max(margin_y, min(y_pos, video_h - text_h - margin_y))
    return x_pos, y_pos

def _safe_caption_position(clip, video_w, video_h, pos_x, pos_y):
    return _safe_caption_position_size(clip.size, video_w, video_h, pos_x, pos_y)


def _ease_out_cubic(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1.0 - (1.0 - x) ** 3


def _ease_in_cubic(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x ** 3


def _caption_motion_at(t: float, duration: float, preset: dict, animate_in: bool, animate_out: bool) -> tuple[float, float]:
    if preset["mode"] == "none":
        return 1.0, 0.0

    fade_duration = max(0.001, min(float(preset["fade"]), duration * 0.45))
    scale = 1.0
    slide_y = 0.0

    if animate_in and t < fade_duration:
        enter = _ease_out_cubic(t / fade_duration)
        scale = float(preset["start_scale"]) + (1.0 - float(preset["start_scale"])) * enter
        slide_y += (1.0 - enter) * float(preset["slide"])

    if animate_out and t > duration - fade_duration:
        exit_progress = _ease_in_cubic((t - (duration - fade_duration)) / fade_duration)
        scale = min(scale, 1.0 - (1.0 - float(preset["end_scale"])) * exit_progress)
        slide_y -= exit_progress * float(preset["slide"]) * 0.35

    return scale, slide_y


def _caption_clip(
    image: Image.Image,
    start: float,
    duration: float,
    x_pos: int,
    y_pos: int,
    animation_name: str,
    animate_in: bool,
    animate_out: bool,
) -> ImageClip:
    preset = CAPTION_ANIMATIONS.get(animation_name, CAPTION_ANIMATIONS["Smooth Pop"])
    base_w, base_h = image.size

    if preset["mode"] == "none" or (not animate_in and not animate_out):
        return (
            ImageClip(np.array(image))
            .with_start(start)
            .with_duration(duration)
            .with_position((x_pos, y_pos))
        )

    def scale_at(t):
        scale, _ = _caption_motion_at(t, duration, preset, animate_in, animate_out)
        return scale

    def position_at(t):
        scale, slide_y = _caption_motion_at(t, duration, preset, animate_in, animate_out)
        return (
            int(x_pos + (base_w - base_w * scale) / 2.0),
            int(y_pos + (base_h - base_h * scale) / 2.0 + slide_y),
        )

    clip = (
        ImageClip(np.array(image))
        .with_start(start)
        .with_duration(duration)
        .resized(scale_at)
        .with_position(position_at)
    )
    fade_duration = min(float(preset["fade"]), max(0.04, duration / 2.5))
    effects = []
    if animate_in and fade_duration > 0:
        effects.append(vfx.FadeIn(fade_duration))
    if animate_out and fade_duration > 0:
        effects.append(vfx.FadeOut(fade_duration))
    if effects:
        clip = clip.with_effects(effects)
    return clip


def create_pro_subtitle_clips(full_text, words, style, video_w, video_h, pos_x, pos_y, animation_name="Smooth Pop"):
    """Create karaoke captions. Animation runs only at phrase enter/exit, not on every active word."""
    words = _normalize_caption_words(words, fallback_text=full_text)
    clean_words = [w["word"].strip() for w in words if w.get("word", "").strip()]
    if not clean_words:
        return []

    clips = []
    visible_words = [w for w in words if w.get("word", "").strip()]
    for active_index, word_info in enumerate(visible_words):
        if not word_info.get("word", "").strip():
            continue
        image = _render_karaoke_caption_image(clean_words, min(active_index, len(clean_words) - 1), style, video_w, video_h)
        x_pos, y_pos = _safe_caption_position_size(image.size, video_w, video_h, pos_x, pos_y)
        duration = max(0.08, word_info["end"] - word_info["start"])
        clip = _caption_clip(
            image,
            word_info["start"],
            duration,
            x_pos,
            y_pos,
            animation_name,
            animate_in=active_index == 0,
            animate_out=active_index == len(visible_words) - 1,
        )
        clips.append(clip)

    return clips

def render_pro_video(
    video_path: str,
    model_name: str,
    style_name: str,
    pos_x: float,
    pos_y: float,
    language: str = None,
    translate: bool = False,
    caption_font_name: str = "Kanit Bold",
    animation_name: str = "Smooth Pop",
    output_suffix="_pro_final"
) -> dict[str, str]:
    style = dict(SUBTITLE_STYLES.get(style_name, SUBTITLE_STYLES["Vibrant TikTok"]))
    style["font"] = CAPTION_FONTS.get(caption_font_name, style["font"])
    print(f"[*] Loading AI ({model_name})...")
    model = ai_models.get_whisper_model(model_name)
    
    transcribe_opts = {"fp16": False, "word_timestamps": True, "verbose": False}
    if language: transcribe_opts["language"] = language
    if translate: transcribe_opts["task"] = "translate"
        
    print(f"[*] Analyzing audio for sync...")
    result = model.transcribe(video_path, **transcribe_opts)
    
    video = VideoFileClip(video_path)
    subtitle_clips = []
    
    # Process each transcribed segment
    for seg in result["segments"]:
        words = seg.get("words", [])
        if not words:
            # Fallback for models without word timestamps
            words = [{"word": seg["text"], "start": seg["start"], "end": seg["end"]}]
            
        # Keep Thai captions as real word groups, not spaced-out characters.
        normalized_words = _normalize_caption_words(words, fallback_text=seg.get("text", ""))
        max_group_size = 3 if _has_thai(seg.get("text", "")) else 5
        i = 0
        while i < len(normalized_words):
            group = normalized_words[i:i + max_group_size]
            group_text = _caption_join([w["word"].strip() for w in group])
            if not group_text.strip():
                i += 1
                continue
                
            group_clips = create_pro_subtitle_clips(group_text, group, style, video.w, video.h, pos_x, pos_y, animation_name)
            subtitle_clips.extend(group_clips)
            i += max_group_size

    output_filename = os.path.splitext(os.path.basename(video_path))[0] + f"{output_suffix}.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    print(f"[*] Rendering final studio quality video...")
    final_video = CompositeVideoClip([video] + subtitle_clips)
    # Using libx264 with high profile for better quality
    final_video.write_videofile(
        output_path, 
        codec="libx264", 
        audio_codec="aac", 
        fps=video.fps, 
        threads=4,
        preset="medium",
        ffmpeg_params=["-crf", "18"] # High quality setting
    )
    
    # Cleanup to ensure files are released
    final_video.close()
    video.close()
    for c in subtitle_clips: 
        try: c.close()
        except: pass
    
    output_basename = os.path.basename(output_path)
    return {
        "output_video": os.path.abspath(output_path),
        "output_url": f"/outputs/{quote(output_basename)}",
    }

# --- Web UI (Glassmorphism Studio v4.5) ---

PAGE = """
<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <title>AI Video Studio Pro v4.5</title>
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;600;700&display=swap" rel="stylesheet">
  <style>
    :root { 
      --primary: #00ffcc; 
      --primary-dark: #00b3a3;
      --bg: #0d0d12; 
      --panel: rgba(20, 20, 29, 0.8); 
      --card: rgba(28, 28, 40, 0.6);
      --text: #f0f0f5;
      --text-dim: #9494a5;
      --accent: #ff3366;
    }
    
    body { 
      font-family: 'Kanit', sans-serif; 
      margin: 0; background: var(--bg); color: var(--text); overflow-x: hidden;
      background-image: url('https://images.unsplash.com/photo-1534796636912-3b95b3ab5986?auto=format&fit=crop&w=1920&q=80');
      background-attachment: fixed;
      background-size: cover;
    }
    
    .overlay {
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: linear-gradient(135deg, rgba(13,13,18,0.95) 0%, rgba(13,13,18,0.85) 100%);
        z-index: -1;
    }
    
    .navbar { 
      background: rgba(0,0,0,0.4); backdrop-filter: blur(15px);
      padding: 1.2rem 3rem; border-bottom: 1px solid rgba(255,255,255,0.1); 
      display: flex; align-items: center; justify-content: space-between;
      position: sticky; top: 0; z-index: 100;
    }
    
    .logo { 
      font-size: 1.8rem; font-weight: 700; 
      background: linear-gradient(135deg, var(--primary), #3399ff);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      display: flex; align-items: center; gap: 12px;
    }
    
    .container { display: grid; grid-template-columns: 540px 1fr; height: calc(100vh - 80px); }
    
    .sidebar { 
      background: var(--panel); backdrop-filter: blur(20px);
      padding: 30px; border-right: 1px solid rgba(255,255,255,0.05); overflow-y: auto;
      scrollbar-width: thin; scrollbar-color: #333 transparent;
    }
    
    .main-content { padding: 40px; display: flex; flex-direction: column; align-items: center; overflow-y: auto; }
    
    .glass-card {
      background: var(--card); border: 1px solid rgba(255,255,255,0.1);
      backdrop-filter: blur(10px);
      border-radius: 24px; padding: 25px; margin-bottom: 24px;
      box-shadow: 0 15px 35px rgba(0,0,0,0.4);
    }
    
    .section-title { 
      font-size: 0.85rem; margin-bottom: 20px; color: var(--primary); 
      text-transform: uppercase; letter-spacing: 2px; display: flex; align-items: center; gap: 12px;
    }
    
    .form-group { margin-bottom: 25px; }
    label { display: block; margin-bottom: 12px; font-size: 0.9rem; color: var(--text-dim); }
    
    input, select { 
      width: 100%; padding: 15px; border-radius: 14px; border: 1px solid #333; 
      background: rgba(0,0,0,0.3); color: #fff; box-sizing: border-box; font-size: 1rem;
      transition: 0.3s;
    }
    input:focus, select:focus { border-color: var(--primary); outline: none; box-shadow: 0 0 15px rgba(0, 255, 204, 0.2); }
    
    .btn { 
      padding: 18px 24px; border-radius: 16px; border: none; font-weight: 600; 
      cursor: pointer; width: 100%; transition: 0.4s; display: flex; align-items: center; justify-content: center; gap: 12px;
      font-size: 1.1rem;
    }
    
    .btn-primary { background: linear-gradient(135deg, var(--primary), #00d4ff); color: #050505; }
    .btn-primary:hover { transform: translateY(-4px); box-shadow: 0 10px 25px rgba(0, 255, 204, 0.4); }
    
    .source-tabs { display: flex; gap: 10px; margin-bottom: 20px; background: rgba(0,0,0,0.5); padding: 6px; border-radius: 16px; }
    .tab { flex: 1; padding: 14px; text-align: center; cursor: pointer; border-radius: 12px; color: var(--text-dim); transition: 0.3s; }
    .tab.active { background: var(--primary); color: #000; font-weight: 600; }
    
    .preview-box { 
      width: 100%; max-width: 960px; aspect-ratio: 16/9; background: #050507; border: 1px solid rgba(255,255,255,0.1); 
      border-radius: 18px; position: relative; overflow: hidden; box-shadow: 0 30px 60px rgba(0,0,0,0.6);
    }
    .preview-box.vertical { aspect-ratio: 9/16; max-width: 420px; }
    .preview-video {
      position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; background: #000;
    }
    .preview-empty {
      position: absolute; inset: 0; display: grid; place-items: center; color: rgba(255,255,255,0.32);
      font-size: 0.95rem; text-align: center; padding: 24px;
    }
    
    .drag-subtitle { 
      position: absolute; bottom: 28%; left: 50%; transform: translateX(-50%); 
      max-width: 88%; min-width: 42%; box-sizing: border-box;
      background: rgba(0,0,0,0.74); padding: 12px 18px; border-radius: 10px; border: 2px dashed var(--primary); 
      cursor: move; color: #fff; font-weight: 900; white-space: normal; font-size: clamp(1.35rem, 3.5vw, 2rem);
      line-height: 1.08; text-align: center; overflow-wrap: anywhere; text-transform: uppercase;
      text-shadow: 0 4px 0 #000, 0 0 18px rgba(37, 255, 106, 0.75);
      user-select: none;
      will-change: opacity, transform;
      transform-origin: center;
    }
    .drag-subtitle .word {
      display: inline-block;
      color: var(--preview-word-color, #fff);
      margin: 0 0.12em;
      transition: color 90ms linear, text-shadow 90ms linear;
    }
    .drag-subtitle .caption-line {
      display: block;
    }
    .drag-subtitle .caption-line + .caption-line {
      margin-top: 0.16em;
      font-size: 0.86em;
    }
    .drag-subtitle .word.active {
      color: var(--preview-highlight-color, #25ff6a);
      text-shadow: 0 4px 0 #000, 0 0 18px var(--preview-highlight-glow, rgba(37, 255, 106, 0.75));
    }
    .drag-subtitle.preview-enter {
      animation: captionPreviewIn var(--preview-enter-ms, 170ms) cubic-bezier(.2,.9,.22,1) both;
    }
    .drag-subtitle.preview-exit {
      animation: captionPreviewOut var(--preview-exit-ms, 150ms) cubic-bezier(.55,0,.72,.18) both;
    }
    .drag-subtitle.preview-none {
      animation: none;
      opacity: 1;
    }
    @keyframes captionPreviewIn {
      from {
        opacity: var(--preview-from-opacity, 0);
        transform: translate(-50%, var(--preview-enter-y, 18px)) scale(var(--preview-start-scale, 0.94));
      }
      to { opacity: 1; transform: translate(-50%, -50%) scale(1); }
    }
    @keyframes captionPreviewOut {
      from { opacity: 1; transform: translate(-50%, -50%) scale(1); }
      to {
        opacity: var(--preview-to-opacity, 0);
        transform: translate(-50%, var(--preview-exit-y, -7px)) scale(var(--preview-end-scale, 0.985));
      }
    }
    .preview-tools { width: 100%; max-width: 960px; margin: 18px 0 0; }
    .preview-actions { display: flex; gap: 12px; margin-top: 12px; }
    .btn-secondary {
      background: rgba(255,255,255,0.08); color: #fff; border: 1px solid rgba(255,255,255,0.14);
      padding: 12px 16px; font-size: 0.95rem; border-radius: 12px;
    }
    
    .style-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    .style-card { 
      border: 1.5px solid #333; padding: 18px; border-radius: 16px; cursor: pointer; 
      text-align: center; background: rgba(0,0,0,0.2); transition: 0.3s;
    }
    .style-card:hover { border-color: var(--primary); }
    .style-card.active { border-color: var(--primary); color: var(--primary); background: rgba(0, 255, 204, 0.1); }
    
    .status { padding: 30px; border-radius: 24px; margin-top: 30px; width: 100%; max-width: 800px; backdrop-filter: blur(10px); }
    .status-ok { background: rgba(0, 255, 204, 0.1); border: 1px solid var(--primary); color: #8ee99a; }
    .status-err { background: rgba(255, 51, 102, 0.1); border: 1px solid var(--accent); color: #ff7675; }
    
    .loader { display: none; margin-top: 30px; text-align: center; }
    .loader i { animation: spin 1s linear infinite; font-size: 3rem; color: var(--primary); margin-bottom: 20px; }
    @keyframes spin { 100% { transform: rotate(360deg); } }
    
    .checkbox-group { display: flex; align-items: center; gap: 12px; color: var(--text-dim); }
    .checkbox-group input { width: 20px; height: 20px; accent-color: var(--primary); }
  </style>
</head>
<body>
  <div class="overlay"></div>
  <div class="navbar">
    <div class="logo"><i class="fas fa-magic"></i> STUDIO PRO v4.5</div>
    <div style="display:flex; gap: 25px; align-items:center;">
      <a href="/advanced" style="color:var(--primary); text-decoration:none; font-weight:700;"><i class="fas fa-layer-group"></i> Advanced Mode</a>
      <span style="color:var(--text-dim);"><i class="fas fa-microchip" style="color:var(--primary)"></i> Ultra Sync Enabled</span>
      <span style="color:var(--text-dim);"><i class="fas fa-bolt"></i> GPU Mastering</span>
    </div>
  </div>
  
  <div class="container">
    <div class="sidebar">
      <form id="processForm" method="post" action="/process">
        <div class="glass-card">
          <div class="section-title"><i class="fas fa-download"></i> 1. นำเข้าวิดีโอ (URL/FILE)</div>
          <div class="source-tabs">
            <div class="tab active" id="tab-url" onclick="setSource('url')">Online Link</div>
            <div class="tab" id="tab-local" onclick="setSource('local')">Local Drive</div>
          </div>
          <input type="hidden" name="source_type" id="source_type" value="url">
          <input name="video_input" id="video_input" placeholder="YouTube, TikTok Link..." required value="{{ video_input }}">
          <button type="button" id="browse_btn" class="btn" style="display:none; border:1.5px solid rgba(255,255,255,0.2); margin-top:15px; color: white;" onclick="browseFile()">
            <i class="fas fa-folder-open"></i> เลือกไฟล์วิดีโอ
          </button>
        </div>
        
        <div class="glass-card">
          <div class="section-title"><i class="fas fa-layer-group"></i> 2. เลือกโหมดการทำงาน</div>
          <div class="form-group">
            <div class="style-grid">
              <div class="style-card active" id="mode-subtitles_only" onclick="setMode('subtitles_only')">
                <i class="fas fa-closed-captioning" style="font-size: 1.5rem; margin-bottom: 8px;"></i><br>ใส่ซับอย่างเดียว
              </div>
              <div class="style-card" id="mode-highlights" onclick="setMode('highlights')">
                <i class="fas fa-cut" style="font-size: 1.5rem; margin-bottom: 8px;"></i><br>ซับ + ตัดไฮไลท์
              </div>
            </div>
            <input type="hidden" name="mode" id="mode" value="subtitles_only">
          </div>
        </div>

        <div class="glass-card">
          <div class="section-title"><i class="fas fa-brain"></i> 3. ปัญญาประดิษฐ์ AI</div>
          <div class="form-group">
            <label>Whisper Sync Model</label>
            <select name="model_name">
              <option value="base">Base (เร็วที่สุด)</option>
              <option value="small">Small (แม่นยำขึ้น)</option>
              <option value="medium">Medium (ระดับโปร)</option>
            </select>
          </div>
          <div class="checkbox-group">
            <input type="checkbox" name="translate" id="translate">
            <label for="translate">แปลเป็นภาษาอังกฤษอัตโนมัติ (AI Translation)</label>
          </div>
        </div>

        <div class="glass-card">
          <div class="section-title"><i class="fas fa-film"></i> 4. สัดส่วนและเวลา</div>
          <div class="form-group">
            <label>ขนาดหน้าจอ (Aspect Ratio)</label>
            <select name="aspect_ratio" id="aspect_ratio">
              <option value="9:16" selected>TikTok / Shorts (9:16)</option>
              <option value="16:9">YouTube Standard (16:9)</option>
            </select>
          </div>

          <div class="form-group" id="duration_group" style="display:none;">
            <label>ความยาวคลิปรวม (วินาที)</label>
            <input type="number" name="max_duration" value="60" min="5" max="300">
          </div>
        </div>
        
        <div class="glass-card">
          <div class="section-title"><i class="fas fa-star"></i> 5. สไตล์ซับไทเทิล (Animation)</div>
          <div class="style-grid">
            <div class="style-card active" id="style-Vibrant TikTok" onclick="setStyle('Vibrant TikTok')">TikTok Vibrant (Pop)</div>
            <div class="style-card" id="style-Gamer Pro" onclick="setStyle('Gamer Pro')">Gamer Pro (Scale)</div>
            <div class="style-card" id="style-Minimal Dark" onclick="setStyle('Minimal Dark')">Minimal Dark</div>
          </div>
          <div class="form-group" style="margin-top:22px;">
            <label>Caption Font</label>
            <select name="caption_font_name" id="caption_font_name" onchange="setPreviewFont(this.value)">
              <option value="Kanit Bold" selected>Kanit Bold</option>
              <option value="Prompt Bold">Prompt Bold</option>
              <option value="Kanit Regular">Kanit Regular</option>
              <option value="Arial">Arial</option>
            </select>
          </div>
          <div class="form-group">
            <label>Caption Animation</label>
            <select name="animation_name" id="animation_name" onchange="restartCaptionPreview()">
              <option value="Smooth Pop" selected>Smooth Pop</option>
              <option value="Slide Fade">Slide Fade</option>
              <option value="Fade Only">Fade Only</option>
              <option value="None">None</option>
            </select>
          </div>
          <input type="hidden" name="style_name" id="style_name" value="Vibrant TikTok">
          <input type="hidden" name="pos_x" id="pos_x" value="0.5">
          <input type="hidden" name="pos_y" id="pos_y" value="0.66">
        </div>
        
        <button type="submit" class="btn btn-primary" onclick="showLoader()">
          <i class="fas fa-magic"></i> ผลิตคลิปสมบูรณ์แบบ
        </button>
        
        <div class="loader" id="loader">
          <i class="fas fa-spinner fa-spin"></i>
          <p style="color:var(--primary); font-weight:600;">กำลังตัดต่อและทำอนิเมชั่นระดับโปร...</p>
          <p id="job_status_text" style="color:var(--text-dim); margin-top:8px;"></p>
        </div>
      </form>
    </div>
    
    <div class="main-content">
      <div class="preview-box vertical" id="preview">
        {% if result and result.output_url %}
        <video class="preview-video" id="preview_video" src="{{ result.output_url }}" controls playsinline></video>
        {% else %}
        <div class="preview-empty" id="preview_empty">Preview will appear here</div>
        <video class="preview-video" id="preview_video" controls playsinline style="display:none;"></video>
        {% endif %}
        <div class="drag-subtitle" id="drag_sub" aria-live="off"></div>
      </div>
      <div class="preview-tools">
        <label for="preview_text">English preview text</label>
        <input id="preview_text" value="MANY PEOPLE THINK THAT" maxlength="90">
        <label for="preview_text_th" style="margin-top:12px;">Thai preview text</label>
        <input id="preview_text_th" value="หลายคนคิดแบบนั้น" maxlength="90">
        <div class="preview-actions">
          <button type="button" class="btn btn-secondary" onclick="restartCaptionPreview()">
            <i class="fas fa-play"></i> Replay Preview
          </button>
        </div>
      </div>
      
      {% if result %}
      <div class="status status-ok">
        <div style="font-size: 1.3rem; font-weight: 700; margin-bottom: 12px; display:flex; align-items:center; gap:12px;">
          <i class="fas fa-check-circle" style="color:var(--primary)"></i> ผลิตเสร็จสิ้น 1 ไฟล์สมบูรณ์แบบ!
        </div>
        <p>ตำแหน่งไฟล์:</p>
        <p><code style="background:#000; padding:12px; border-radius:12px; display:block; margin-top:10px; font-size:0.9rem; border:1px solid #333;">{{ result.output_video }}</code></p>
        <video src="{{ result.output_url }}" controls playsinline style="width:100%; max-height:70vh; margin-top:16px; border-radius:14px; background:#000;"></video>
      </div>
      {% endif %}
      
      {% if error %}
      <div class="status status-err">
        <div style="font-size: 1.2rem; font-weight: 700; margin-bottom: 12px;">
          <i class="fas fa-exclamation-triangle"></i> พบข้อผิดพลาด
        </div>
        <p>{{ error }}</p>
      </div>
      {% endif %}

      <div class="status status-ok" id="async_result" style="display:none;">
        <div style="font-size: 1.3rem; font-weight: 700; margin-bottom: 12px; display:flex; align-items:center; gap:12px;">
          <i class="fas fa-check-circle" style="color:var(--primary)"></i> Render completed
        </div>
        <p>Output file:</p>
        <p><code id="async_output_path" style="background:#000; padding:12px; border-radius:12px; display:block; margin-top:10px; font-size:0.9rem; border:1px solid #333;"></code></p>
        <video id="async_output_video" controls playsinline style="width:100%; max-height:70vh; margin-top:16px; border-radius:14px; background:#000;"></video>
      </div>

      <div class="status status-err" id="async_error" style="display:none;">
        <div style="font-size: 1.2rem; font-weight: 700; margin-bottom: 12px;">
          <i class="fas fa-exclamation-triangle"></i> Render failed
        </div>
        <p id="async_error_text"></p>
      </div>
      
      <div style="margin-top: 50px; text-align: center; opacity: 0.5; max-width: 600px;">
        <p><i class="fas fa-info-circle"></i> ระบบใช้ AI ในการ Master ทุกขั้นตอน ตั้งแต่การตัดต่อไฮไลท์ การจัดกึ่งกลางภาพสำหรับ TikTok และการทำอนิเมชั่นซับไทเทิลแบบเรียลไทม์</p>
      </div>
    </div>
  </div>

  <script>
    const previewStylePresets = {
      'Vibrant TikTok': {
        color: '#fff',
        highlight: '#25ff6a',
        glow: 'rgba(37,255,106,0.75)',
        shadow: '0 4px 0 #000, 0 0 18px rgba(37,255,106,0.75)',
        bg: 'rgba(0,0,0,0.74)'
      },
      'Gamer Pro': {
        color: '#fff',
        highlight: '#fff200',
        glow: 'rgba(255,242,0,0.8)',
        shadow: '4px 4px 0 #000, 0 0 16px rgba(255,242,0,0.45)',
        bg: 'rgba(0,0,0,0.78)'
      },
      'Minimal Dark': {
        color: '#fff',
        highlight: '#25ff6a',
        glow: 'rgba(37,255,106,0.45)',
        shadow: '0 3px 0 #000',
        bg: 'rgba(0,0,0,0.58)'
      }
    };

    const previewAnimationPresets = {
      'Smooth Pop': { enterMs: 170, exitMs: 150, startScale: 0.94, endScale: 0.985, enterY: '18px', exitY: '-7px', fromOpacity: 0, toOpacity: 0 },
      'Slide Fade': { enterMs: 190, exitMs: 170, startScale: 1, endScale: 1, enterY: '30px', exitY: '-10px', fromOpacity: 0, toOpacity: 0 },
      'Fade Only': { enterMs: 150, exitMs: 140, startScale: 1, endScale: 1, enterY: '-50%', exitY: '-50%', fromOpacity: 0, toOpacity: 0 },
      'None': { enterMs: 0, exitMs: 0, startScale: 1, endScale: 1, enterY: '-50%', exitY: '-50%', fromOpacity: 1, toOpacity: 1 }
    };

    let previewTimer = null;
    let previewRunId = 0;

    function setSource(type) {
      document.getElementById('source_type').value = type;
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.getElementById('tab-' + type).classList.add('active');
      const input = document.getElementById('video_input');
      const browseBtn = document.getElementById('browse_btn');
      if(type === 'url') {
        input.placeholder = 'YouTube/TikTok Link...';
        input.readOnly = false;
        browseBtn.style.display = 'none';
      } else {
        input.placeholder = 'เลือกไฟล์วิดีโอจากเครื่อง';
        input.readOnly = true;
        browseBtn.style.display = 'block';
      }
    }

    function setMode(mode) {
      document.getElementById('mode').value = mode;
      document.querySelectorAll('[id^="mode-"]').forEach(m => m.classList.remove('active'));
      document.getElementById('mode-' + mode).classList.add('active');
      const durationGroup = document.getElementById('duration_group');
      if(mode === 'highlights') {
        durationGroup.style.display = 'block';
      } else {
        durationGroup.style.display = 'none';
      }
    }

    async function browseFile() {
      const resp = await fetch('/api/browse');
      const data = await resp.json();
      if(data.file_path) {
        document.getElementById('video_input').value = data.file_path;
        setPreviewVideo(data.file_path);
      }
    }

    function setPreviewVideo(filePath) {
      const video = document.getElementById('preview_video');
      const empty = document.getElementById('preview_empty');
      if(!video || !filePath) return;
      video.src = '/preview-file?path=' + encodeURIComponent(filePath);
      video.style.display = 'block';
      if(empty) empty.style.display = 'none';
      video.load();
    }

    function setStyle(name) {
      document.getElementById('style_name').value = name;
      document.querySelectorAll('.style-card').forEach(c => c.classList.remove('active'));
      document.getElementById('style-' + name).classList.add('active');
      applyPreviewStyle();
      restartCaptionPreview();
    }

    function setPreviewFont(name) {
      const sub = document.getElementById('drag_sub');
      if(name.includes('Prompt')) sub.style.fontFamily = "'Prompt', 'Kanit', sans-serif";
      else if(name.includes('Arial')) sub.style.fontFamily = "Arial, sans-serif";
      else sub.style.fontFamily = "'Kanit', sans-serif";
      sub.style.fontWeight = name.includes('Regular') ? '700' : '900';
      restartCaptionPreview();
    }

    function splitPreviewText(value, fallback) {
      const text = (value || fallback).trim();
      const hasSpaces = /\s/.test(text);
      if(hasSpaces) return text.split(/\s+/).filter(Boolean).slice(0, 8);
      return Array.from(text).filter(ch => ch.trim()).slice(0, 12);
    }

    function getPreviewLines() {
      return [
        splitPreviewText(document.getElementById('preview_text').value, 'MANY PEOPLE THINK THAT'),
        splitPreviewText(document.getElementById('preview_text_th').value, 'หลายคนคิดแบบนั้น')
      ].filter(line => line.length);
    }

    function getPreviewWordCount() {
      return getPreviewLines().reduce((sum, line) => sum + line.length, 0);
    }

    function renderPreviewWords(activeIndex = -1) {
      const sub = document.getElementById('drag_sub');
      const lines = getPreviewLines();
      let cursor = 0;
      sub.innerHTML = '';
      lines.forEach((words) => {
        const line = document.createElement('span');
        line.className = 'caption-line';
        words.forEach((word, index) => {
          const span = document.createElement('span');
          span.className = 'word' + (cursor === activeIndex ? ' active' : '');
          span.textContent = /[a-z]/i.test(word) ? word.toUpperCase() : word;
          line.appendChild(span);
          if(index < words.length - 1) line.appendChild(document.createTextNode(' '));
          cursor += 1;
        });
        sub.appendChild(line);
      });
    }

    function applyPreviewStyle() {
      const styleName = document.getElementById('style_name').value || 'Vibrant TikTok';
      const preset = previewStylePresets[styleName] || previewStylePresets['Vibrant TikTok'];
      const sub = document.getElementById('drag_sub');
      sub.style.setProperty('--preview-word-color', preset.color);
      sub.style.setProperty('--preview-highlight-color', preset.highlight);
      sub.style.setProperty('--preview-highlight-glow', preset.glow);
      sub.style.textShadow = preset.shadow;
      sub.style.background = preset.bg;
    }

    function applyPreviewAnimationVars() {
      const animationName = document.getElementById('animation_name').value || 'Smooth Pop';
      const preset = previewAnimationPresets[animationName] || previewAnimationPresets['Smooth Pop'];
      const sub = document.getElementById('drag_sub');
      sub.style.setProperty('--preview-enter-ms', preset.enterMs + 'ms');
      sub.style.setProperty('--preview-exit-ms', preset.exitMs + 'ms');
      sub.style.setProperty('--preview-start-scale', preset.startScale);
      sub.style.setProperty('--preview-end-scale', preset.endScale);
      sub.style.setProperty('--preview-enter-y', preset.enterY);
      sub.style.setProperty('--preview-exit-y', preset.exitY);
      sub.style.setProperty('--preview-from-opacity', preset.fromOpacity);
      sub.style.setProperty('--preview-to-opacity', preset.toOpacity);
    }

    function clearCaptionPreviewTimers() {
      if(previewTimer) {
        clearTimeout(previewTimer);
        previewTimer = null;
      }
      previewRunId += 1;
    }

    function restartCaptionPreview() {
      clearCaptionPreviewTimers();
      applyPreviewStyle();
      applyPreviewAnimationVars();
      const sub = document.getElementById('drag_sub');
      const animationName = document.getElementById('animation_name').value || 'Smooth Pop';
      const preset = previewAnimationPresets[animationName] || previewAnimationPresets['Smooth Pop'];
      const runId = previewRunId;
      const wordCount = Math.max(1, getPreviewWordCount());
      const wordMs = 430;
      const holdMs = 250;

      sub.classList.remove('preview-enter', 'preview-exit', 'preview-none');
      renderPreviewWords(-1);
      void sub.offsetWidth;

      if(animationName === 'None') {
        sub.classList.add('preview-none');
      } else {
        sub.classList.add('preview-enter');
      }

      Array.from({ length: wordCount }).forEach((_, index) => {
        setTimeout(() => {
          if(runId !== previewRunId) return;
          renderPreviewWords(index);
        }, preset.enterMs + index * wordMs);
      });

      const exitAt = preset.enterMs + wordCount * wordMs + holdMs;
      setTimeout(() => {
        if(runId !== previewRunId) return;
        renderPreviewWords(-1);
        if(animationName !== 'None') {
          sub.classList.remove('preview-enter');
          void sub.offsetWidth;
          sub.classList.add('preview-exit');
        }
      }, exitAt);

      previewTimer = setTimeout(() => {
        if(runId !== previewRunId) return;
        restartCaptionPreview();
      }, exitAt + preset.exitMs + 650);
    }

    document.getElementById('aspect_ratio').addEventListener('change', (e) => {
      const preview = document.getElementById('preview');
      if(e.target.value === '9:16') preview.classList.add('vertical');
      else preview.classList.remove('vertical');
    });

    const drag_sub = document.getElementById('drag_sub');
    const preview = document.getElementById('preview');
    const previewText = document.getElementById('preview_text');
    const previewTextTh = document.getElementById('preview_text_th');
    let dragging = false;
    if(previewText) {
      previewText.addEventListener('input', () => {
        restartCaptionPreview();
      });
    }
    if(previewTextTh) {
      previewTextTh.addEventListener('input', () => {
        restartCaptionPreview();
      });
    }
    drag_sub.addEventListener('mousedown', (e) => { dragging = true; e.preventDefault(); });
    drag_sub.addEventListener('touchstart', (e) => { dragging = true; e.preventDefault(); }, { passive: false });
    window.addEventListener('mouseup', () => dragging = false);
    window.addEventListener('touchend', () => dragging = false);
    function moveSubtitle(clientX, clientY) {
      if(!dragging) return;
      const rect = preview.getBoundingClientRect();
      let x = clientX - rect.left - (drag_sub.offsetWidth / 2);
      let y = clientY - rect.top - (drag_sub.offsetHeight / 2);
      x = Math.max(0, Math.min(x, rect.width - drag_sub.offsetWidth));
      y = Math.max(0, Math.min(y, rect.height - drag_sub.offsetHeight));
      drag_sub.style.left = (x + (drag_sub.offsetWidth/2)) + 'px';
      drag_sub.style.top = (y + (drag_sub.offsetHeight/2)) + 'px';
      drag_sub.style.transform = 'translate(-50%, -50%)';
      document.getElementById('pos_x').value = ((x + drag_sub.offsetWidth / 2) / rect.width).toFixed(4);
      document.getElementById('pos_y').value = ((y + drag_sub.offsetHeight / 2) / rect.height).toFixed(4);
    }
    window.addEventListener('mousemove', (e) => {
      moveSubtitle(e.clientX, e.clientY);
    });
    window.addEventListener('touchmove', (e) => {
      if(e.touches.length) moveSubtitle(e.touches[0].clientX, e.touches[0].clientY);
    });

    const initialJobId = {{ job_id|default('', true)|tojson }};

    function showLoader(message) {
      document.getElementById('loader').style.display = 'block';
      const statusText = document.getElementById('job_status_text');
      if(statusText) statusText.textContent = message || 'Queued.';
    }

    function setJobMessage(message) {
      const statusText = document.getElementById('job_status_text');
      if(statusText) statusText.textContent = message || '';
    }

    function showAsyncResult(result) {
      if(!result || !result.output_url) {
        showAsyncError('Render finished, but the output path was not returned.');
        return;
      }
      const previewEmpty = document.getElementById('preview_empty');
      const previewVideo = document.getElementById('preview_video');
      if(previewEmpty) previewEmpty.style.display = 'none';
      const cacheBust = result.output_url.includes('?') ? `&t=${Date.now()}` : `?t=${Date.now()}`;
      const outputUrl = result.output_url + cacheBust;
      if(previewVideo) {
        previewVideo.src = outputUrl;
        previewVideo.style.display = 'block';
        previewVideo.load();
      }

      document.getElementById('loader').style.display = 'none';
      document.getElementById('async_error').style.display = 'none';
      document.getElementById('async_output_path').textContent = result.output_video;
      const outputVideo = document.getElementById('async_output_video');
      outputVideo.src = outputUrl;
      outputVideo.load();
      document.getElementById('async_result').style.display = 'block';
      document.getElementById('async_result').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function showAsyncError(message) {
      document.getElementById('loader').style.display = 'none';
      document.getElementById('async_result').style.display = 'none';
      document.getElementById('async_error_text').textContent = message || 'Unknown error';
      document.getElementById('async_error').style.display = 'block';
    }

    async function pollJob(jobId) {
      showLoader('Queued.');
      try {
        const resp = await fetch(`/api/jobs/${jobId}?t=${Date.now()}`, { cache: 'no-store' });
        if(!resp.ok) throw new Error('Job was not found.');
        const job = await resp.json();
        setJobMessage(job.message || job.status);
        if(job.status === 'done') {
          showAsyncResult(job.result);
          return;
        }
        if(job.status === 'error') {
          showAsyncError(job.message);
          return;
        }
        setTimeout(() => pollJob(jobId), 1200);
      } catch(err) {
        showAsyncError(err.message);
      }
    }

    async function restoreLatestOutput() {
      try {
        const resp = await fetch(`/api/latest-output?t=${Date.now()}`, { cache: 'no-store' });
        if(!resp.ok) return;
        const result = await resp.json();
        showAsyncResult(result);
      } catch(err) {
        console.warn('Could not restore latest output', err);
      }
    }

    document.getElementById('processForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      document.getElementById('async_result').style.display = 'none';
      document.getElementById('async_error').style.display = 'none';
      showLoader('Submitting job...');
      try {
        const formData = new FormData(event.currentTarget);
        const resp = await fetch('/api/process', { method: 'POST', body: formData });
        const data = await resp.json();
        if(!resp.ok) throw new Error(data.error || 'Could not start job.');
        pollJob(data.job_id);
      } catch(err) {
        showAsyncError(err.message);
      }
    });

    if(initialJobId) pollJob(initialJobId);
    else restoreLatestOutput();
    setPreviewFont(document.getElementById('caption_font_name').value);
    applyPreviewStyle();
    restartCaptionPreview();
  </script>
</body>
</html>
"""

ADVANCED_PAGE = """
<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <title>AI Video Studio Advanced</title>
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;600;700&display=swap" rel="stylesheet">
  <style>
    :root { --primary:#00ffcc; --blue:#4aa3ff; --bg:#0d0d12; --panel:rgba(22,22,32,.88); --card:rgba(32,32,46,.72); --text:#f4f4f7; --dim:#9d9dae; --danger:#ff4f73; }
    body { margin:0; font-family:'Kanit',sans-serif; color:var(--text); background:#0d0d12; }
    body:before { content:""; position:fixed; inset:0; z-index:-2; background:url('https://images.unsplash.com/photo-1516035069371-29a1b244cc32?auto=format&fit=crop&w=1920&q=80') center/cover; }
    body:after { content:""; position:fixed; inset:0; z-index:-1; background:linear-gradient(135deg,rgba(8,8,12,.96),rgba(8,12,18,.90)); }
    .nav { height:72px; display:flex; align-items:center; justify-content:space-between; padding:0 34px; background:rgba(0,0,0,.45); border-bottom:1px solid rgba(255,255,255,.1); position:sticky; top:0; z-index:5; }
    .logo { font-size:1.35rem; font-weight:800; color:var(--primary); display:flex; align-items:center; gap:12px; }
    a { color:var(--primary); text-decoration:none; }
    .layout { display:grid; grid-template-columns:520px 1fr; min-height:calc(100vh - 72px); }
    .sidebar { padding:28px; background:var(--panel); border-right:1px solid rgba(255,255,255,.08); overflow:auto; }
    .stage { padding:34px; overflow:auto; }
    .card { background:var(--card); border:1px solid rgba(255,255,255,.1); border-radius:14px; padding:22px; margin-bottom:20px; box-shadow:0 18px 48px rgba(0,0,0,.35); }
    .title { color:var(--primary); text-transform:uppercase; letter-spacing:1.3px; font-size:.82rem; font-weight:800; margin-bottom:16px; display:flex; gap:10px; align-items:center; }
    label { color:var(--dim); display:block; margin:12px 0 8px; font-size:.92rem; }
    input, textarea, select { width:100%; box-sizing:border-box; color:#fff; background:rgba(0,0,0,.38); border:1px solid rgba(255,255,255,.13); border-radius:10px; padding:13px; font:inherit; }
    textarea { min-height:122px; resize:vertical; line-height:1.45; }
    .row { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    .btn { width:100%; border:0; border-radius:12px; padding:15px 18px; font-weight:800; cursor:pointer; display:flex; justify-content:center; align-items:center; gap:10px; font-size:1rem; }
    .primary { background:linear-gradient(135deg,var(--primary),var(--blue)); color:#050508; }
    .ghost { background:rgba(255,255,255,.08); color:#fff; border:1px solid rgba(255,255,255,.12); }
    .hint { color:var(--dim); font-size:.86rem; line-height:1.5; margin-top:10px; }
    .preview { background:#000; border:1px solid rgba(255,255,255,.12); border-radius:14px; overflow:hidden; width:100%; max-width:980px; aspect-ratio:16/9; display:grid; place-items:center; color:rgba(255,255,255,.35); }
    .preview.vertical { max-width:430px; aspect-ratio:9/16; margin:auto; }
    video { width:100%; height:100%; object-fit:contain; background:#000; }
    .loader { display:none; text-align:center; color:var(--primary); padding:22px; }
    .loader i { animation:spin 1s linear infinite; font-size:2.1rem; }
    @keyframes spin { to { transform:rotate(360deg); } }
    .status { display:none; padding:18px; border-radius:12px; margin-top:18px; }
    .ok { background:rgba(0,255,204,.1); border:1px solid var(--primary); }
    .err { background:rgba(255,79,115,.11); border:1px solid var(--danger); color:#ff9aae; }
    .timeline { display:grid; gap:10px; margin-top:18px; max-width:980px; }
    .shot { background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.1); border-radius:12px; padding:14px; }
    .shot strong { color:var(--primary); }
    .metric { color:var(--dim); font-size:.85rem; margin-top:6px; }
    .checkbox { display:flex; align-items:center; gap:10px; margin:14px 0; color:var(--dim); }
    .checkbox input { width:18px; height:18px; }
  </style>
</head>
<body>
  <div class="nav">
    <div class="logo"><i class="fas fa-layer-group"></i> AI Video Studio Advanced</div>
    <div><a href="/"><i class="fas fa-arrow-left"></i> Standard Mode</a></div>
  </div>
  <div class="layout">
    <aside class="sidebar">
      <form id="advancedForm">
        <div class="card">
          <div class="title"><i class="fas fa-film"></i> 1. Multi-video sources</div>
          <label>Video paths, one per line</label>
          <textarea name="video_paths" id="video_paths" placeholder="C:\\path\\video1.mp4&#10;C:\\path\\video2.mp4" required></textarea>
          <div class="hint">Advanced Mode analyzes every source, scores the best speech/audio/visual moments, then builds one cut.</div>
        </div>
        <div class="card">
          <div class="title"><i class="fas fa-comments"></i> 2. Editing brief</div>
          <label>What should the cut feel like or talk about?</label>
          <textarea name="brief" placeholder="เช่น ช่วงที่พูดประเด็นสำคัญ มีภาพเคลื่อนไหวเยอะ และน้ำเสียงเริ่มพีค"></textarea>
        </div>
        <div class="card">
          <div class="title"><i class="fas fa-sliders"></i> 3. Output controls</div>
          <div class="row">
            <div>
              <label>Whisper model</label>
              <select name="model_name"><option value="base">Base</option><option value="small">Small</option><option value="medium">Medium</option></select>
            </div>
            <div>
              <label>Aspect ratio</label>
              <select name="aspect_ratio" id="aspect_ratio"><option value="9:16">9:16 Shorts</option><option value="16:9">16:9 Landscape</option></select>
            </div>
          </div>
          <div class="row">
            <div>
              <label>Target seconds</label>
              <input name="target_duration" type="number" value="45" min="5" max="300">
            </div>
            <div>
              <label>Language hint</label>
              <input name="language" placeholder="th / en / blank">
            </div>
          </div>
          <label class="checkbox"><input type="checkbox" name="add_subtitles" checked> Add automatic subtitles after the advanced cut</label>
          <div class="row">
            <div>
              <label>Caption font</label>
              <select name="caption_font_name"><option>Kanit Bold</option><option>Prompt Bold</option><option>Kanit Regular</option></select>
            </div>
            <div>
              <label>Animation</label>
              <select name="animation_name"><option>Smooth Pop</option><option>Slide Fade</option><option>Fade Only</option><option>None</option></select>
            </div>
          </div>
          <input type="hidden" name="style_name" value="Vibrant TikTok">
        </div>
        <button class="btn primary" type="submit"><i class="fas fa-wand-magic-sparkles"></i> Analyze & Build Advanced Cut</button>
      </form>
      <div class="loader" id="loader"><i class="fas fa-spinner"></i><p id="jobText">Queued.</p></div>
      <div class="status err" id="errorBox"></div>
    </aside>
    <main class="stage">
      <div class="preview vertical" id="preview"><span>Advanced preview will appear here</span></div>
      <div class="status ok" id="resultBox">
        <strong>Advanced edit completed</strong>
        <p id="outputPath"></p>
      </div>
      <div class="timeline" id="timeline"></div>
    </main>
  </div>
  <script>
    const form = document.getElementById('advancedForm');
    const loader = document.getElementById('loader');
    const jobText = document.getElementById('jobText');
    const errorBox = document.getElementById('errorBox');
    const resultBox = document.getElementById('resultBox');
    const preview = document.getElementById('preview');
    const timeline = document.getElementById('timeline');
    const aspect = document.getElementById('aspect_ratio');

    aspect.addEventListener('change', () => {
      preview.classList.toggle('vertical', aspect.value === '9:16');
    });

    function showError(message) {
      loader.style.display = 'none';
      errorBox.textContent = message || 'Unknown error';
      errorBox.style.display = 'block';
    }

    function renderResult(result) {
      loader.style.display = 'none';
      errorBox.style.display = 'none';
      resultBox.style.display = 'block';
      document.getElementById('outputPath').textContent = result.output_video;
      const url = result.output_url + (result.output_url.includes('?') ? '&' : '?') + 't=' + Date.now();
      preview.innerHTML = `<video src="${url}" controls playsinline></video>`;

      const selected = (result.analysis && result.analysis.selected) || [];
      timeline.innerHTML = selected.map((shot, index) => `
        <div class="shot">
          <strong>${index + 1}. Source ${shot.source_index + 1} | ${shot.start.toFixed(2)}s - ${shot.end.toFixed(2)}s</strong>
          <div>${shot.text || ''}</div>
          <div class="metric">${shot.reason} | score ${shot.score.toFixed(2)} | audio ${shot.audio_score.toFixed(2)} | visual ${shot.visual_score.toFixed(2)}</div>
        </div>
      `).join('');
    }

    async function poll(jobId) {
      try {
        const resp = await fetch(`/api/jobs/${jobId}?t=${Date.now()}`, { cache: 'no-store' });
        if(!resp.ok) throw new Error('Job not found');
        const job = await resp.json();
        jobText.textContent = job.message || job.status;
        if(job.status === 'done') return renderResult(job.result);
        if(job.status === 'error') return showError(job.message);
        setTimeout(() => poll(jobId), 1200);
      } catch(err) {
        showError(err.message);
      }
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      loader.style.display = 'block';
      resultBox.style.display = 'none';
      errorBox.style.display = 'none';
      timeline.innerHTML = '';
      jobText.textContent = 'Submitting advanced analysis...';
      try {
        const resp = await fetch('/api/advanced/process', { method:'POST', body:new FormData(form) });
        const data = await resp.json();
        if(!resp.ok) throw new Error(data.error || 'Could not start Advanced Mode');
        poll(data.job_id);
      } catch(err) {
        showError(err.message);
      }
    });
  </script>
</body>
</html>
"""

@app.get("/")
def index():
    return render_template_string(PAGE, result=None, error=None, video_input="", job_id="")


@app.get("/advanced")
def advanced_index():
    return render_template_string(ADVANCED_PAGE)

@app.get("/api/browse")
def api_browse():
    return jsonify({"file_path": utils.select_file_dialog()})

@app.get("/outputs/<path:filename>")
def serve_output(filename):
    output_root = os.path.abspath(OUTPUT_DIR)
    file_path = os.path.abspath(os.path.join(output_root, filename))
    if not file_path.startswith(output_root + os.sep) or not os.path.exists(file_path):
        abort(404)
    return send_file(file_path, conditional=True)

@app.get("/preview-file")
def preview_file():
    file_path = os.path.abspath(request.args.get("path", "").strip().strip('"').strip("'"))
    allowed_ext = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}
    if os.path.splitext(file_path)[1].lower() not in allowed_ext or not os.path.exists(file_path):
        abort(404)
    return send_file(file_path, conditional=True)


@app.post("/api/process")
def api_process():
    try:
        params = _parse_process_form(request.form)
        job_id = _start_job(params)
        return jsonify({"job_id": job_id, "status": "queued"}), 202
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/advanced/process")
def api_advanced_process():
    try:
        params = _parse_advanced_form(request.form)
        job_id = _start_advanced_job(params)
        return jsonify({"job_id": job_id, "status": "queued"}), 202
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.get("/api/jobs/<job_id>")
def api_job(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            abort(404)
        return jsonify(_public_job(job))


@app.get("/api/latest-output")
def api_latest_output():
    result = _latest_output_result()
    if not result:
        abort(404)
    return jsonify(result)


@app.post("/process")
def process():
    try:
        params = _parse_process_form(request.form)
        job_id = _start_job(params)
        return render_template_string(PAGE, result=None, error=None, video_input=params["video_input"], job_id=job_id)
    except Exception as e:
        traceback.print_exc()
        video_input = request.form.get("video_input", "").strip().strip('"').strip("'")
        return render_template_string(PAGE, result=None, error=str(e), video_input=video_input, job_id="")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)

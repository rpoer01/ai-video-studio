from __future__ import annotations

import os
import uuid
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from moviepy import (
    AudioFileClip,
    ColorClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
)

import font_manager


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".aac", ".m4a", ".ogg", ".flac"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


LANG_COLORS = {
    "th": "#38f8c9",
    "en": "#ffd166",
    "other": "#ffffff",
}


def _subclip(media, start: float, end: float):
    if hasattr(media, "subclipped"):
        return media.subclipped(start, end)
    return media.subclip(start, end)


def _resized(media, **kwargs):
    if hasattr(media, "resized"):
        return media.resized(**kwargs)
    return media.resize(**kwargs)


def _with_start(media, value: float):
    if hasattr(media, "with_start"):
        return media.with_start(value)
    return media.set_start(value)


def _with_duration(media, value: float):
    if hasattr(media, "with_duration"):
        return media.with_duration(value)
    return media.set_duration(value)


def _with_position(media, value):
    if hasattr(media, "with_position"):
        return media.with_position(value)
    return media.set_position(value)


def _with_opacity(media, value: float):
    if hasattr(media, "with_opacity"):
        return media.with_opacity(value)
    return media.set_opacity(value)


def _with_audio(media, audio):
    if hasattr(media, "with_audio"):
        return media.with_audio(audio)
    return media.set_audio(audio)


def _volume_scaled(audio, value: float):
    if hasattr(audio, "with_volume_scaled"):
        return audio.with_volume_scaled(value)
    return audio.volumex(value)


def _resolve_source_path(path_value: str, project_root: str) -> Path:
    path = Path(str(path_value or "")).expanduser()
    if path.is_absolute():
        return path
    return (Path(project_root) / path).resolve()


def _fit_media(media, width: int, height: int):
    if media.w == 0 or media.h == 0:
        return media
    scale = min(width / media.w, height / media.h)
    return _resized(media, width=max(1, int(media.w * scale)), height=max(1, int(media.h * scale)))


def _text_image(text: str, style: dict, canvas_w: int, canvas_h: int):
    font_size = int(style.get("fontSize", 54))
    font = font_manager.load_font(font_size)
    stroke_width = int(style.get("strokeWidth", max(1, font_size * 0.06)))
    color = style.get("color", "#ffffff")
    stroke_color = style.get("strokeColor", "#000000")
    shadow = bool(style.get("shadow", True))
    align = style.get("align", "center")

    scratch = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    draw = ImageDraw.Draw(scratch)
    words = style.get("words") if isinstance(style.get("words"), list) else []
    if words:
        text = "".join(
            str(word.get("text") or word.get("word") or "")
            + ("" if word.get("lang") == "th" and index + 1 < len(words) and words[index + 1].get("lang") == "th" else " ")
            for index, word in enumerate(words)
        ).strip()

    bbox = draw.multiline_textbbox(
        (0, 0),
        text,
        font=font,
        spacing=8,
        align=align,
        stroke_width=stroke_width,
    )
    text_w = max(1, bbox[2] - bbox[0])
    text_h = max(1, bbox[3] - bbox[1])
    pad = max(24, int(font_size * 0.55))

    img = Image.new("RGBA", (text_w + pad * 2, text_h + pad * 2), (0, 0, 0, 0))
    x = pad - bbox[0]
    y = pad - bbox[1]

    if shadow:
        shadow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        shadow_draw.multiline_text(
            (x + 6, y + 8),
            text,
            font=font,
            fill=(0, 0, 0, 170),
            spacing=8,
            align=align,
            stroke_width=stroke_width + 2,
            stroke_fill=(0, 0, 0, 170),
        )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=8))
        img = Image.alpha_composite(img, shadow_layer)

    text_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)
    if words:
        cursor = x
        baseline = y
        for index, word in enumerate(words):
            token = str(word.get("text") or word.get("word") or "").strip()
            if not token:
                continue
            fill = LANG_COLORS.get(word.get("lang", "other"), color)
            text_draw.text(
                (cursor, baseline),
                token,
                font=font,
                fill=fill,
                stroke_width=stroke_width,
                stroke_fill=stroke_color,
            )
            token_bbox = text_draw.textbbox((cursor, baseline), token, font=font, stroke_width=stroke_width)
            cursor = token_bbox[2]
            next_word = words[index + 1] if index + 1 < len(words) else None
            if next_word and not (word.get("lang") == "th" and next_word.get("lang") == "th"):
                cursor += int(font_size * 0.32)
    else:
        text_draw.multiline_text(
            (x, y),
            text,
            font=font,
            fill=color,
            spacing=8,
            align=align,
            stroke_width=stroke_width,
            stroke_fill=stroke_color,
        )
    img = Image.alpha_composite(img, text_layer)
    return np.array(img)


def _normalized_position(style: dict, canvas_w: int, canvas_h: int):
    x = float(style.get("x", 50))
    y = float(style.get("y", 80))
    x = max(0.0, min(100.0, x))
    y = max(0.0, min(100.0, y))
    return (int(canvas_w * (x / 100.0)), int(canvas_h * (y / 100.0)))


def _project_duration(project: dict) -> float:
    total = 0.0
    for track in project.get("tracks", []):
        for clip in track.get("clips", []):
            if clip.get("hidden"):
                continue
            total = max(total, float(clip.get("start", 0.0)) + float(clip.get("duration", 0.0)))
    return max(1.0, total)


def render_project(project: dict, export_dir: str, project_root: str) -> str:
    resolution = project.get("resolution", {}) or {}
    width = int(resolution.get("width", 1280))
    height = int(resolution.get("height", 720))
    fps = int(project.get("fps", 30))
    duration = _project_duration(project)

    layers = []
    audio_layers = []
    open_media = []
    final = None

    try:
        background = _with_duration(ColorClip(size=(width, height), color=(10, 12, 18)), duration)
        layers.append(background)

        for track in project.get("tracks", []):
            if track.get("hidden") or track.get("locked"):
                continue

            track_kind = track.get("kind", "")
            for clip in track.get("clips", []):
                if clip.get("hidden"):
                    continue

                clip_start = max(0.0, float(clip.get("start", 0.0)))
                clip_duration = max(0.05, float(clip.get("duration", 0.0)))
                style = clip.get("style", {}) or {}

                if track_kind in {"video", "image"}:
                    source_path = _resolve_source_path(clip.get("sourcePath"), project_root)
                    if not source_path.exists():
                        continue

                    ext = source_path.suffix.lower()
                    if ext in IMAGE_EXTENSIONS or clip.get("type") == "image":
                        media = ImageClip(str(source_path))
                        media = _with_duration(media, clip_duration)
                    else:
                        media = VideoFileClip(str(source_path))
                        open_media.append(media)
                        source_in = max(0.0, float(clip.get("sourceIn", 0.0)))
                        source_out = min(float(media.duration), source_in + clip_duration)
                        media = _subclip(media, source_in, source_out)

                    media = _fit_media(media, width, height)
                    media = _with_position(media, ("center", "center"))
                    media = _with_start(media, clip_start)
                    media = _with_duration(media, clip_duration)

                    opacity = float(style.get("opacity", 1.0))
                    if opacity < 1.0:
                        media = _with_opacity(media, opacity)

                    layers.append(media)
                    if getattr(media, "audio", None) is not None:
                        audio = _with_start(media.audio, clip_start)
                        volume = float(style.get("volume", 1.0))
                        if volume != 1.0:
                            audio = _volume_scaled(audio, volume)
                        audio_layers.append(audio)

                elif track_kind == "audio":
                    source_path = _resolve_source_path(clip.get("sourcePath"), project_root)
                    if not source_path.exists():
                        continue
                    audio = AudioFileClip(str(source_path))
                    open_media.append(audio)
                    source_in = max(0.0, float(clip.get("sourceIn", 0.0)))
                    source_out = min(float(audio.duration), source_in + clip_duration)
                    audio = _subclip(audio, source_in, source_out)
                    audio = _with_start(audio, clip_start)
                    volume = float(style.get("volume", 1.0))
                    if volume != 1.0:
                        audio = _volume_scaled(audio, volume)
                    audio_layers.append(audio)

                elif track_kind in {"subtitle", "text", "effect"}:
                    text = str(clip.get("text") or clip.get("name") or "").strip()
                    if not text:
                        continue
                    style = dict(style)
                    if clip.get("words"):
                        style["words"] = clip.get("words")
                    img = _text_image(text, style, width, height)
                    text_clip = ImageClip(img)
                    text_clip = _with_duration(text_clip, clip_duration)
                    text_clip = _with_start(text_clip, clip_start)
                    position = _normalized_position(style, width, height)
                    text_clip = _with_position(text_clip, position)
                    opacity = float(style.get("opacity", 1.0))
                    if opacity < 1.0:
                        text_clip = _with_opacity(text_clip, opacity)
                    layers.append(text_clip)

        final = CompositeVideoClip(layers, size=(width, height))
        if audio_layers:
            final = _with_audio(final, CompositeAudioClip(audio_layers))

        Path(export_dir).mkdir(parents=True, exist_ok=True)
        output_path = Path(export_dir) / f"editor_export_{uuid.uuid4().hex[:8]}.mp4"
        final.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=fps,
            threads=4,
            logger=None,
        )
        return str(output_path)
    finally:
        if final is not None:
            try:
                final.close()
            except Exception:
                pass
        for media in layers:
            if hasattr(media, "close"):
                try:
                    media.close()
                except Exception:
                    pass
        for media in open_media:
            try:
                media.close()
            except Exception:
                pass

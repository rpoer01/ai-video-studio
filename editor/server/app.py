from __future__ import annotations

import json
import mimetypes
import os
import queue
import sys
import traceback
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    import assemblyai as aai
except Exception:
    aai = None

from editor.server.services.render_service import render_project
from editor.server.services.subtitle_segmenter import join_tokens, segment_words


APP_DIR = Path(__file__).resolve().parent
EDITOR_DIR = APP_DIR.parent
WEB_DIR = EDITOR_DIR / "web"
UPLOAD_DIR = EDITOR_DIR / "uploads"
EXPORT_DIR = EDITOR_DIR / "exports"
PROJECTS_DIR = EDITOR_DIR / "projects"

for path in (UPLOAD_DIR, EXPORT_DIR, PROJECTS_DIR):
    path.mkdir(parents=True, exist_ok=True)

ASSEMBLYAI_API_KEY = os.environ.get("ASSEMBLYAI_API_KEY", "350bc0bb49d943768b559c72b0c74922")
if aai:
    aai.settings.api_key = ASSEMBLYAI_API_KEY

app = Flask(
    __name__,
    static_folder=str(WEB_DIR / "static"),
    static_url_path="/editor/static",
)

SYNC_CLIENTS: set[queue.Queue] = set()
SYNC_HISTORY: list[dict] = []


@app.after_request
def add_editor_cache_headers(response):
    if request.path.startswith(("/editor/static/", "/editor/uploads/", "/editor/exports/")):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


def publish_sync(event: str, payload: dict):
    message = {"event": event, "payload": payload}
    SYNC_HISTORY.append(message)
    del SYNC_HISTORY[:-50]
    for client in tuple(SYNC_CLIENTS):
        try:
            client.put_nowait(message)
        except Exception:
            SYNC_CLIENTS.discard(client)


def infer_media_kind(filename: str, mime_type: str | None) -> str:
    ext = Path(filename or "").suffix.lower()
    if (mime_type or "").startswith("video/") or ext in {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}:
        return "video"
    if (mime_type or "").startswith("audio/") or ext in {".mp3", ".wav", ".aac", ".m4a", ".ogg", ".flac"}:
        return "audio"
    if (mime_type or "").startswith("image/") or ext in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
        return "image"
    return "file"


def project_path(project_id: str) -> Path:
    safe_id = "".join(char for char in project_id if char.isalnum() or char in {"-", "_"})
    return PROJECTS_DIR / f"{safe_id}.json"


def build_subtitle_track(media_path: str, language_code: str = "th", max_words: int = 3) -> list[dict]:
    if not aai:
        raise RuntimeError("assemblyai package is not installed.")
    if not os.path.exists(media_path):
        raise FileNotFoundError(f"Media file not found: {media_path}")

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(
        media_path,
        config=aai.TranscriptionConfig(language_code=language_code),
    )
    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(transcript.error or "AssemblyAI transcription failed.")

    words = [
        {
            "word": word.text,
            "start": float(word.start) / 1000.0,
            "end": float(word.end) / 1000.0,
        }
        for word in (transcript.words or [])
    ]
    chunks = segment_words(words, max_words=max_words, max_gap=0.45)

    clips = []
    for index, chunk in enumerate(chunks):
        if not chunk:
            continue
        start = float(chunk[0]["start"])
        end = float(chunk[-1]["end"])
        text = join_tokens(chunk)
        if not text:
            continue
        clips.append(
            {
                "id": f"sub-{uuid.uuid4().hex[:10]}",
                "type": "subtitle",
                "name": f"Subtitle {index + 1}",
                "text": text,
                "start": start,
                "duration": max(0.12, end - start),
                "sourceIn": 0,
                "groupId": None,
                "style": {
                    "x": 50,
                    "y": 82,
                    "fontSize": 54,
                    "color": "#ffffff",
                    "strokeColor": "#000000",
                    "strokeWidth": 4,
                    "shadow": True,
                    "opacity": 1,
                    "animation": "karaoke",
                    "highlightColor": "#2dd4bf",
                },
                "words": [
                    {
                        "text": item["word"],
                        "start": float(item["start"]) - start,
                        "end": float(item["end"]) - start,
                        "lang": item.get("lang", "other"),
                    }
                    for item in chunk
                ],
                "segments": [
                    {
                        "lang": item.get("lang", "other"),
                        "text": item["word"],
                        "start": float(item["start"]) - start,
                        "end": float(item["end"]) - start,
                    }
                    for item in chunk
                ],
            }
        )
    return clips


@app.route("/editor")
def editor_index():
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/editor/uploads/<path:filename>")
def serve_editor_upload(filename: str):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/editor/exports/<path:filename>")
def serve_editor_export(filename: str):
    return send_from_directory(EXPORT_DIR, filename)


@app.route("/api/health")
def health():
    return jsonify({"ok": True, "editor": True})


@app.route("/api/realtime/stream")
def realtime_stream():
    client: queue.Queue = queue.Queue(maxsize=100)
    SYNC_CLIENTS.add(client)

    def events():
        try:
            yield "event: ready\ndata: {}\n\n"
            while True:
                try:
                    message = client.get(timeout=20)
                    yield f"event: {message['event']}\ndata: {json.dumps(message['payload'], ensure_ascii=False)}\n\n"
                except queue.Empty:
                    yield "event: ping\ndata: {}\n\n"
        finally:
            SYNC_CLIENTS.discard(client)

    return Response(events(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/media/upload", methods=["POST"])
def upload_media():
    if "file" not in request.files:
        return jsonify({"error": "No file supplied"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    media_id = uuid.uuid4().hex[:12]
    ext = Path(file.filename).suffix
    saved_name = f"{media_id}{ext}"
    save_path = UPLOAD_DIR / saved_name
    file.save(save_path)

    mime_type = file.mimetype or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
    kind = infer_media_kind(file.filename, mime_type)
    asset = {
        "id": media_id,
        "name": file.filename,
        "filename": saved_name,
        "path": str(save_path),
        "url": f"/editor/uploads/{saved_name}",
        "kind": kind,
        "mimeType": mime_type,
        "size": save_path.stat().st_size,
    }
    publish_sync("asset_uploaded", {"asset": asset})
    return jsonify(asset)


@app.route("/api/project/save", methods=["POST"])
def save_project():
    payload = request.get_json(force=True, silent=True) or {}
    project = payload.get("project")
    if not isinstance(project, dict):
        return jsonify({"error": "Missing project payload"}), 400

    project_id = project.get("id") or f"project-{uuid.uuid4().hex[:8]}"
    project["id"] = project_id
    path = project_path(project_id)
    path.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    publish_sync("project_saved", {"projectId": project_id, "project": project})
    return jsonify({"projectId": project_id, "path": str(path)})


@app.route("/api/project/<project_id>")
def load_project(project_id: str):
    path = project_path(project_id)
    if not path.exists():
        return jsonify({"error": "Project not found"}), 404
    data = json.loads(path.read_text(encoding="utf-8"))
    return jsonify({"project": data})


@app.route("/api/project/list")
def list_projects():
    items = []
    for path in sorted(PROJECTS_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items.append({"id": data.get("id"), "name": data.get("name") or path.stem})
        except Exception:
            items.append({"id": path.stem, "name": path.stem})
    return jsonify({"projects": items[:30]})


@app.route("/api/auto-subtitle", methods=["POST"])
def auto_subtitle():
    payload = request.get_json(force=True, silent=True) or {}
    media_path = payload.get("mediaPath")
    if not media_path:
        return jsonify({"error": "Missing mediaPath"}), 400

    try:
        clips = build_subtitle_track(
            media_path=media_path,
            language_code=payload.get("languageCode", "th"),
            max_words=int(payload.get("maxWords", 3)),
        )
        publish_sync("subtitle_created", {"mediaPath": media_path, "clipCount": len(clips), "clips": clips})
        return jsonify({"clips": clips})
    except Exception as exc:
        return jsonify({"error": str(exc), "trace": traceback.format_exc()}), 500


@app.route("/api/export", methods=["POST"])
def export_project():
    payload = request.get_json(force=True, silent=True) or {}
    project = payload.get("project")
    if not isinstance(project, dict):
        return jsonify({"error": "Missing project payload"}), 400

    try:
        output_path = render_project(project, str(EXPORT_DIR), str(ROOT_DIR))
    except Exception as exc:
        return jsonify({"error": str(exc), "trace": traceback.format_exc()}), 500

    return jsonify(
        {
            "outputPath": output_path,
            "outputUrl": f"/editor/exports/{Path(output_path).name}",
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)

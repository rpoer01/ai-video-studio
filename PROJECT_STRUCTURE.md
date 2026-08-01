# AI Video Studio Pro — โครงสร้างและคำอธิบายไฟล์

โปรเจกต์ระบบตัดต่อวิดีโออัตโนมัติด้วย AI รองรับภาษาไทย  
**ฟีเจอร์:** ถอดเสียง/ทำซับไทเทิล (karaoke) + ตัดไฮไลท์อัตโนมัติ + ตัดต่อหลายคลิปขั้นสูง

---

## สารบัญ

1. [ภาพรวม Architecture](#1-ภาพรวม-architecture)
2. [ไฟล์ในโฟลเดอร์หลัก `edit/`](#2-ไฟล์ในโฟลเดอร์หลัก-edit)
3. [Submodule `editor/` (Timeline Editor)](#3-submodule-editor-timeline-editor)
4. [Flow การทำงานหลัก](#4-flow-การทำงานหลัก)
5. [ตารางสรุป API Endpoints](#5-ตารางสรุป-api-endpoints)

---

## 1. ภาพรวม Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        main.py (Flask Web App)                  │
│  - UI หน้าเว็บ (Jinja2 Template)                                 │
│  - Karaoke Caption Render Engine                                │
│  - Job Queue System (async)                                     │
│  - Routes: /process, /api/process, /advanced, /editor           │
└──────────┬────────────────────────────────────────────────┬─────┘
           │                                                │
           ▼                                                ▼
┌──────────────────────┐                       ┌──────────────────────┐
│   ai_models.py       │                       │  highlight_engine.py │
│  - Whisper (local)   │                       │  - Keyword detection │
│  - AssemblyAI (cloud)│                       │  - Audio peak detect │
│                      │                       │  - Segment planning  │
│                      │                       │  - Extract/cut video │
│                      │                       │  - Download via yt-dlp│
└──────────────────────┘                       └──────────┬───────────┘
           │                                                │
           ▼                                                ▼
┌──────────────────────┐                       ┌──────────────────────┐
│  highlight_pipeline  │                       │advanced_video_analyze│
│  = engine + pipeline │                       │ = Multi-source       │
│  เชื่อม AI + highlight│                       │   speech+audio+visual│
│  ตัดคลิปไฮไลท์       │                       │   scoring + render   │
└──────────────────────┘                       └──────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    editor/server/app.py                         │
│  - Backend API สำหรับ Timeline Editor                           │
│  - Media upload / import URL (yt-dlp)                           │
│  - Save/Load project JSON                                       │
│  - Auto subtitle (AssemblyAI) → subtitle track                  │
│  - Export / Render timeline                                     │
│  - Real-time sync (SSE)                                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. ไฟล์ในโฟลเดอร์หลัก `edit/`

### 2.1 `main.py` — Web Application + Karaoke Engine (2232 บรรทัด)

**บทบาท:** จุดศูนย์กลางของระบบ — เป็นทั้ง Web UI และ ตัวเรนเดอร์ซับไทเทิลแบบคาราโอเกะ

**โครงสร้างภายใน:**

| ส่วน | บรรทัด | หน้าที่ |
|------|--------|---------|
| Config & Setup | 1–68 | ตั้งค่า ImageMagick, FFmpeg, Flask app, ThreadPool |
| Job Queue | 67–98 | ระบบ async job (`JOBS` dict + `ThreadPoolExecutor`) |
| Form Parsers | 100–172 | แปลงฟอร์ม HTML → params dict |
| `_produce_video()` | 176–226 | **Pipeline หลัก:** ดาวน์โหลด → ตัดไฮไลท์ → ใส่ซับ |
| `_produce_advanced_video()` | 229–269 | **Pipeline Advanced:** วิเคราะห์หลายคลิป → ตัด → ใส่ซับ |
| Karaoke Caption Engine | 382–868 | ระบบเรนเดอร์ซับไทเทิลที่สำคัญที่สุด |
|  - Style Presets | 385–427 | 3 สไตล์ซับ: Vibrant TikTok, Gamer Pro, Minimal Dark |
|  - Thai Tokenizer | 466–511 | แยกคำไทยด้วย pythainlp (fallback เอง) |
|  - Audio Alignment | 551–595 | จับคู่คำกับพลังงานเสียงจริงด้วย librosa |
|  - Karaoke Frame Render | 687–733 | เรนเดอร์ภาพซับต่อเฟรม (highlight คำที่ active) |
|  - Animation Engine | 759–827 | animation pop/slide/fade |
|  - `render_pro_video()` | 870–984 | ฟังก์ชันหลัก: transcribe → group words → render composite |
| Web UI (HTML+CSS+JS) | 988–2039 | 2 หน้า: main form + advanced form |
| Routes | 2041–2232 | `/`, `/advanced`, `/process`, `/api/*`, `/editor/*` |

**API Routes ใน main.py:**

| Route | Method | หน้าที่ |
|-------|--------|--------|
| `/` | GET | หน้าแรก (ฟอร์มหลัก) |
| `/advanced` | GET | หน้า Advanced Mode |
| `/editor` | GET | เปิด Timeline Editor |
| `/api/process` | POST | Submit งาน (async) → คืน job_id |
| `/api/advanced/process` | POST | Submit งาน Advanced Mode |
| `/api/jobs/<id>` | GET | ตรวจสอบสถานะงาน |
| `/api/latest-output` | GET | ไฟล์ล่าสุดที่สร้าง |
| `/api/browse` | GET | เปิด file dialog (Windows) |
| `/api/editor/export` | POST | Export จาก Pro Editor |
| `/api/editor/asset-info` | GET | ข้อมูลไฟล์มีเดีย |
| `/outputs/<path>` | GET | serve ไฟล์ output |
| `/preview-file` | GET | serve ไฟล์ preview |

---

### 2.2 `ai_models.py` — AI Transcription Models (58 บรรทัด)

**บทบาท:** จัดการโมเดล AI สำหรับถอดเสียง → ข้อความ

| ฟังก์ชัน | หน้าที่ |
|----------|---------|
| `get_whisper_model(name)` | โหลด Whisper (caching) — tiny/base/small/medium/large |
| `transcribe_with_assemblyai(path, lang)` | ถอดเสียงผ่าน AssemblyAI Cloud API → segments + words |

**API Key AssemblyAI:** `350bc0bb49d943768b559c72b0c74922` (hardcoded)

---

### 2.3 `highlight_engine.py` — Core Highlight Engine (567 บรรทัด)

**บทบาท:** ตรวจจับช่วงเวลาสำคัญของวิดีโอ วางแผนตัด และตัดคลิป

| ฟังก์ชัน | หน้าที่ |
|----------|---------|
| `download_video(url)` | ดาวน์โหลดจาก YouTube/TikTok/Facebook ด้วย yt-dlp |
| `detect_highlights_by_keywords(segments, category)` | ค้นหาคำสำคัญภาษาไทย (สุดยอด, เดือด, พีค, ฯลฯ) |
| `detect_highlights_by_audio(video_path)` | หาช่วงที่เสียงดังเกิน threshold (audio peak) |
| `build_transcript_candidates(segments)` | สร้าง candidate จากคำพูด (backup) |
| `merge_segments(segments, max_gap)` | รวม segment ที่ใกล้กัน |
| `plan_highlight_segments(...)` | **วางแผน:** เลือก segment ที่ดีที่สุด → ให้ได้ความยาวตาม target |
| `smooth_segments_to_transcript(...)` | ปรับขอบ segment ให้ตรงกับช่วงพูด (ไม่ตัดกลางคำ) |
| `extract_highlights(video_path, segments, ...)` | **ตัดคลิปจริง:** subclip + crop 9:16 + concatenate |

**Categories ของคำค้นหา:**
- General: สวย, สุดยอด, ดีมาก, ว้าว, โอ้โห
- Gaming: แตก, ยับ, คม, โหด, Triple Kill, Ace
- Vlog/Review: น่าสนใจ, แนะนำ, ห้ามพลาด, คุ้ม
- Business/News: สำคัญ, วิเคราะห์, เติบโต, กำไร

---

### 2.4 `highlight_pipeline.py` — Highlight Pipeline (65 บรรทัด)

**บทบาท:** เชื่อมต่อ AI + Highlight Engine ใน pipeline เดียว

| ฟังก์ชัน | หน้าที่ |
|----------|---------|
| `cut_highlight_video(...)` | Transcribe → detect keywords + audio → plan → smooth → extract → คืน output_path |

**Flow:** `AssemblyAI (หรือ Whisper fallback)` → `detect_highlights_by_keywords` + `detect_highlights_by_audio` → `plan_highlight_segments` → `smooth_segments_to_transcript` → `extract_highlights`

---

### 2.5 `advanced_video_analyzer.py` — Advanced Multi-Source Analyzer (321 บรรทัด)

**บทบาท:** วิเคราะห์และตัดต่อวิดีโอจาก **หลายแหล่ง** โดยใช้ 3 ปัจจัย: เสียงพูด + ระดับเสียง + การเคลื่อนไหวของภาพ

| ฟังก์ชัน | หน้าที่ |
|----------|---------|
| `_semantic_score(text, prompt_terms)` | คะแนนความตรงกับ brief ที่ผู้ใช้กำหนด |
| `_audio_profile(video)` | วิเคราะห์โปรไฟล์เสียง (พลังงาน RMS ตลอดคลิป) |
| `_visual_profile(video_path, duration)` | วิเคราะห์โปรไฟล์ภาพ (motion + contrast + brightness) |
| `_build_candidates(...)` | สร้าง candidate segments จาก transcript + คะแนนทั้ง 3 ด้าน |
| `_select_candidates(candidates, target)` | เลือก candidate คะแนนสูงสุด → ให้ได้ความยาวตาม target |
| `_render_selected(selected, aspect)` | ตัด + crop 9:16 + ต่อคลิป |
| `analyze_and_render(...)` | ฟังก์ชันหลัก: วนลูปทุก source → transcribe → score → select → render |

**Multi-Factor Scoring Formula:**
```
score = semantic * 3.0 + audio_score * 1.6 + visual_score * 1.25 + intro_bias
```

---

### 2.6 `utils.py` — Utilities (67 บรรทัด)

| ฟังก์ชัน | หน้าที่ |
|----------|---------|
| `download_required_fonts(target_dir)` | ดาวน์โหลดฟอนต์ไทย Kanit/Prompt จาก GitHub |
| `select_file_dialog()` | เปิด Windows File Explorer ให้เลือกไฟล์วิดีโอ |

**ฟอนต์ที่ใช้:** Kanit-Bold, Kanit-Regular, Prompt-Bold

---

### 2.7 `check_tools.py` — System Readiness Checker (73 บรรทัด)

**บทบาท:** ตรวจสอบเครื่องมือที่จำเป็นก่อนรันโปรเจกต์

| ฟังก์ชัน | ตรวจสอบ |
|----------|---------|
| `check_ffmpeg()` | FFmpeg ใน PATH + imageio_ffmpeg |
| `check_imagemagick()` | ImageMagick ใน PATH + ตำแหน่งติดตั้ง Windows |
| `check_python_libs()` | whisper, moviepy, PIL, yt_dlp, pythainlp, cv2 |

---

### 2.8 `font_manager.py` — Font Loader (19 บรรทัด)

โหลดฟอนต์ Kanit-Bold จากตำแหน่งต่างๆ (fallback → arial.ttf → default)

---

### 2.9 `process_highlights_cli.py` — CLI Highlight Cutter (99 บรรทัด)

**บทบาท:** รันตัดไฮไลท์จาก command line โดยไม่ต้องเปิดเว็บ

```
python process_highlights_cli.py <video/url> --model base --category Gaming --max-duration 60
```

---

### 2.10 `process_video_cli.py` — CLI Subtitle Burner (192 บรรทัด)

**บทบาท:** รันถอดเสียง + เบิร์นซับไทเทิล (.srt + ลงวิดีโอ) จาก command line

**Hardcoded:** ใช้ไฟล์ `C:\Users\zazqi\OneDrive\Desktop\wwwwaad\2026-04-04 23-16-28.mp4`

---

### 2.11 `requirements.txt` — Dependencies

```
flask, imageio-ffmpeg, moviepy, numpy, opencv-python,
openai-whisper, pillow, pythainlp, requests, yt-dlp, assemblyai
```

---

## 3. Submodule `editor/` (Timeline Editor)

โฟลเดอร์แยกสำหรับ Timeline-based Video Editor (CapCut-style)  
**แยกจาก main.py** — ใช้ Flask API ของตัวเอง

### 3.1 `editor/server/app.py` — Editor Backend API (370 บรรทัด)

**บทบาท:** Backend สำหรับ Timeline Editor — จัดการ media, project, subtitle, export

| Route | Method | หน้าที่ |
|-------|--------|--------|
| `/api/health` | GET | Health check |
| `/api/realtime/stream` | GET | SSE real-time sync |
| `/api/media/upload` | POST | อัปโหลดไฟล์มีเดีย |
| `/api/media/import-url` | POST | ดาวน์โหลดจาก URL (yt-dlp) |
| `/api/project/save` | POST | บันทึกโปรเจค (JSON) |
| `/api/project/<id>` | GET | โหลดโปรเจค |
| `/api/project/list` | GET | รายชื่อโปรเจค |
| `/api/auto-subtitle` | POST | สร้าง subtitle track จาก AssemblyAI |
| `/api/export` | POST | เรนเดอร์ timeline → วิดีโอ |

### 3.2 `editor/server/services/render_service.py` — Timeline Renderer (364 บรรทัด)

**บทบาท:** เรนเดอร์ JSON timeline → ไฟล์วิดีโอ (.mp4)

**รองรับ track types:**
- `video` / `image` → VideoFileClip / ImageClip + crop/resize
- `audio` → AudioFileClip
- `subtitle` / `text` / `effect` → PIL render + ImageClip (รองรับ karaoke word-by-word)

### 3.3 `editor/server/services/subtitle_segmenter.py` — Thai Word Segmenter (126 บรรทัด)

**บทบาท:** แยกคำภาษาไทย/อังกฤษในซับไทเทิล, จัดกลุ่มคำ, join tokens

| ฟังก์ชัน | หน้าที่ |
|----------|---------|
| `language_of(text)` | เช็คว่าเป็น th / en / other |
| `normalize_words(words)` | แยกคำผสมไทย-อังกฤษ → tokens พร้อมภาษา |
| `segment_words(words, max_words, max_gap)` | จัดกลุ่ม tokens → chunks (ตามภาษา+จำนวน+ระยะห่าง) |
| `join_tokens(tokens)` | รวม tokens กลับเป็นข้อความ (เว้นวรรคเฉพาะภาษาอังกฤษ) |

---

## 4. Flow การทำงานหลัก

### 4.1 โหมดปกติ (Subtitles + Highlights)

```
User → main.py (Web UI)
  ├── Input: URL หรือ Local file
  ├── download_video() ← yt-dlp (ถ้าเป็น URL)
  ├── [Highlights mode] → highlight_pipeline.cut_highlight_video()
  │     ├── ai_models.transcribe_with_assemblyai() → segments
  │     ├── detect_highlights_by_keywords() → keyword segments
  │     ├── detect_highlights_by_audio() → audio peak segments
  │     ├── plan_highlight_segments() → select + merge
  │     ├── smooth_segments_to_transcript() → adjust boundaries
  │     └── extract_highlights() → output.mp4 (9:16 cropped)
  │
  ├── render_pro_video() → Karaoke Subtitle Engine
  │     ├── transcribe (AssemblyAI / Whisper) → segments + words
  │     ├── phrase group (3-5 words)
  │     ├── Real-time sync: _align_thai_tokens_with_audio() ← librosa
  │     ├── For each word group:
  │     │     ├── _render_karaoke_caption_image() → PIL image
  │     │     └── _caption_clip() → ImageClip + animation
  │     └── CompositeVideoClip() → output_final.mp4
  │
  └── Return → แสดง preview ในหน้าเว็บ
```

### 4.2 โหมด Advanced (Multi-Source)

```
User → main.py (Advanced UI)
  ├── Input: หลาย video paths + brief text
  ├── analyze_and_render()
  │     ├── สำหรับแต่ละ source:
  │     │     ├── Transcribe → segments
  │     │     ├── _audio_profile() ← RMS energy
  │     │     ├── _visual_profile() ← motion + contrast + brightness
  │     │     └── _build_candidates() ← score = semantic + audio + visual
  │     ├── _select_candidates() ← best segments รวมกันให้ได้ target_duration
  │     └── _render_selected() ← subclip + crop 9:16 + concatenate
  │
  └── (Optional) render_pro_video() → ใส่ซับไทเทิล
```

### 4.3 Timeline Editor Mode

```
User → /editor (editor/web/index.html)
  ├── Upload media → /api/media/upload
  ├── Import URL → /api/media/import-url (yt-dlp)
  ├── ลากวางบน Timeline (JS frontend)
  ├── Auto subtitle → /api/auto-subtitle → subtitle track
  ├── Save/Load → /api/project/save, /api/project/<id>
  └── Export → /api/export → render_service.render_project()
        ├── CompositeVideoClip(tracks)
        └── write_videofile() → output.mp4
```

---

## 5. ตารางสรุป API Endpoints

| Endpoint | Method | จากไฟล์ | หน้าที่ |
|----------|--------|---------|--------|
| `/` | GET | main.py | หน้าเว็บหลัก |
| `/advanced` | GET | main.py | หน้า Advanced Mode |
| `/editor` | GET | main.py | เปิด Timeline Editor |
| `/process` | POST | main.py | ส่งฟอร์ม (SSR) |
| `/api/process` | POST | main.py | Submit job (async) |
| `/api/advanced/process` | POST | main.py | Submit advanced job |
| `/api/jobs/<id>` | GET | main.py | เช็คสถานะ job |
| `/api/latest-output` | GET | main.py | ไฟล์ output ล่าสุด |
| `/api/browse` | GET | main.py | เปิด file dialog |
| `/api/editor/export` | POST | main.py | Export จาก Pro Editor |
| `/outputs/<path>` | GET | main.py | Serve ไฟล์ output |
| `/preview-file` | GET | main.py | Serve preview |
| `/api/health` | GET | editor/server/app.py | Health check |
| `/api/media/upload` | POST | editor/server/app.py | อัปโหลดมีเดีย |
| `/api/media/import-url` | POST | editor/server/app.py | ดาวน์โหลดจาก URL |
| `/api/project/save` | POST | editor/server/app.py | บันทึกโปรเจค |
| `/api/project/<id>` | GET | editor/server/app.py | โหลดโปรเจค |
| `/api/project/list` | GET | editor/server/app.py | รายชื่อโปรเจค |
| `/api/auto-subtitle` | POST | editor/server/app.py | สร้าง subtitle tracks |
| `/api/export` | POST | editor/server/app.py | เรนเดอร์ timeline |
| `/api/realtime/stream` | GET | editor/server/app.py | SSE sync |

---

## หมายเหตุ

- **AssemblyAI API Key** ถูก hardcode ไว้ใน `ai_models.py` และ `editor/server/app.py` — ควรเปลี่ยนเป็น environment variable
- **ฟอนต์ Kanit/Prompt** ดาวน์โหลดอัตโนมัติจาก Google Fonts โดย `utils.py`
- **ImageMagick** จำเป็นสำหรับ MoviePy TextClip (ติดตั้งที่ `C:\Program Files\ImageMagick-*`)
- **รองรับภาษาไทย** โดยเฉพาะ — มี fallback tokenizer สำหรับภาษาไทยโดยเฉพาะ, keyword dictionary ภาษาไทย, และการจัดระยะห่างคำไทย

# AI Video Studio Pro — Phase 1: Foundation

## โครงสร้างไฟล์ใหม่

```
edit/
├── core/                     # ระบบหลัก
│   ├── __init__.py
│   ├── ai_chat.py           # AI Chat Interface (สื่อสารกับ AI)
│   └── pipeline_manager.py  # Pipeline Manager (จัด workflow)
│
├── analyzers/                # ระบบวิเคราะห์
│   ├── __init__.py
│   ├── text_analyzer.py     # วิเคราะห์ข้อความ
│   └── image_analyzer.py    # วิเคราะห์ภาพ
│
├── plugins/                  # AI Provider System
│   ├── __init__.py
│   ├── base.py              # Abstract Base + Registry
│   └── openai_provider.py   # OpenAI Provider
│
├── pipelines/                # Pipeline definitions
│   └── (will add more)
│
├── api/                      # FastAPI endpoints
│   └── (will add later)
│
└── (existing files)
```

## สิ่งที่สร้างแล้ว

### 1. AI Chat Interface (`core/ai_chat.py`)
- ช่องทางสื่อสารกับ AI ผ่าน chat
- ตรวจจับ intent จากข้อความ (analyze, highlight, subtitle, cut, effect)
- รองรับ context (video_path, etc.)
- ตัวอย่าง:
```python
from core.ai_chat import AIChatInterface

chat = AIChatInterface()
response = chat.send("ช่วยวิเคราะห์วีดีโอนี้ให้หน่อย", {"video_path": "test.mp4"})
```

### 2. Text Analyzer (`analyzers/text_analyzer.py`)
- วิเคราะห์ transcript จาก AI transcription
- หาคำสำคัญ (keywords) แยกตามหมวดหมู่
- วิเคราะห์อารมณ์จากข้อความ
- จัดกลุ่มคำสำหรับซับไทเทิล
- หาช่วงที่สำคัญ (important segments)
- ตัวอย่าง:
```python
from analyzers.text_analyzer import TextAnalyzer

analyzer = TextAnalyzer()
result = analyzer.analyze(transcript)
highlights = analyzer.get_highlights(max_highlights=5)
```

### 3. Image Analyzer (`analyzers/image_analyzer.py`)
- วิเคราะห์ภาพจากวีดีโอ
- ตรวจจับวัตถุ (Object Detection)
- จำแนกฉาก (Scene Classification)
- วิเคราะห์อารมณ์ (Mood Analysis)
- จับคู่ภาพกับข้อความ
- ตัวอย่าง:
```python
from analyzers.image_analyzer import ImageAnalyzer, MoodType

analyzer = ImageAnalyzer(use_ai_vision=True)
result = analyzer.analyze_frame("frame.jpg")
matching = analyzer.find_matching_scenes(frames, MoodType.HAPPY)
```

### 4. Plugin System (`plugins/`)
- Abstract Base สำหรับ AI Provider
- Provider Registry (ลงทะเบียน/ค้นหา Provider)
- OpenAI Provider (GPT-4V, Whisper, GPT-4)
- ตัวอย่าง:
```python
from plugins.base import get_best_provider, ProviderType
from plugins.openai_provider import OpenAIProvider

# ลงทะเบียน
provider = OpenAIProvider(config=ProviderConfig(api_key="..."))
register_provider(provider)

# ใช้งาน
best = get_best_provider(ProviderType.VISION)
result = best.analyze_image("image.jpg")
```

### 5. Pipeline Manager (`core/pipeline_manager.py`)
- สร้าง Pipeline จาก steps
- execute Pipeline แบบ sequential
- ติดตามสถานะและเวลา
- ตัวอย่าง:
```python
from core.pipeline_manager import create_video_analysis_pipeline

pipeline = create_video_analysis_pipeline("video.mp4")
result = pipeline.execute()
```

## ขั้นตอนถัดไป

1. **FastAPI API** — สร้าง REST API สำหรับ Web UI
2. **Database** — ตั้ง SQLite สำหรับเก็บ project data
3. **Frontend** — สร้าง Web UI ใหม่ (Vue.js/React)
4. **Integration** — เชื่อมต่อกับโค้ดเดิม (main.py, highlight_engine.py)

"""
FastAPI API — REST API สำหรับ AI Video Studio
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import uuid
import shutil

app = FastAPI(
    title="AI Video Studio Pro",
    description="ระบบตัดต่อด้วย AI อัตโนมัติ",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class ChatRequest(BaseModel):
    message: str
    video_path: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str
    intent: str
    suggestions: List[str]

class AnalyzeRequest(BaseModel):
    video_path: str
    options: Optional[Dict[str, Any]] = None

class HighlightRequest(BaseModel):
    video_path: str
    max_highlights: int = 5
    category: str = "general"

class SubtitleRequest(BaseModel):
    video_path: str
    style: str = "normal"  # normal, karaoke, tiktok
    language: str = "th"

# In-memory storage (จะเปลี่ยนเป็น DB จริง)
projects: Dict[str, Dict[str, Any]] = {}
jobs: Dict[str, Dict[str, Any]] = {}

# Upload directory
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.get("/")
async def root():
    """หน้าแรก"""
    return {
        "name": "AI Video Studio Pro",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "chat": "/api/chat",
            "analyze": "/api/analyze",
            "highlights": "/api/highlights",
            "subtitle": "/api/subtitle",
            "projects": "/api/projects"
        }
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    สื่อสารกับ AI ผ่าน chat
    
    ตัวอย่าง:
    - "ช่วยวิเคราะห์วีดีโอนี้ให้หน่อย"
    - "หาไฮไลท์จากคลิปนี้"
    - "ใส่ซับไทเทิลให้หน่อย"
    """
    from core.ai_chat import AIChatInterface
    
    chat = AIChatInterface()
    response = chat.send(request.message, {"video_path": request.video_path})
    intent = chat._detect_intent(request.message)
    
    # แนะนำคำสั่งเพิ่มเติม
    suggestions = _get_suggestions(intent)
    
    return ChatResponse(
        response=response,
        intent=intent,
        suggestions=suggestions
    )


@app.post("/api/analyze")
async def analyze_video(request: AnalyzeRequest):
    """
    วิเคราะห์วีดีโอ
    
    Returns:
    - scenes: ฉากทั้งหมด
    - highlights: ไฮไลท์
    - transcript: ข้อความที่ถอดได้
    - emotions: อารมณ์
    """
    from core.pipeline_manager import create_video_analysis_pipeline
    
    # สร้าง pipeline
    pipeline = create_video_analysis_pipeline(request.video_path)
    
    # Execute
    try:
        result = pipeline.execute()
        return {
            "status": "success",
            "pipeline_id": pipeline.id,
            "duration": pipeline.get_duration(),
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/highlights")
async def find_highlights(request: HighlightRequest):
    """
    หาไฮไลท์จากวีดีโอ
    
    Args:
    - video_path: ไฟล์วีดีโอ
    - max_highlights: จำนวนไฮไลท์สูงสุด
    - category: หมวดหมู่ (general, gaming, vlog, review)
    """
    from analyzers.text_analyzer import TextAnalyzer
    from highlight_engine import detect_highlights_by_keywords, detect_highlights_by_audio
    
    try:
        # ถอดเสียง (จำลอง)
        transcript = []  # ในจริงจะเรียก AI transcription
        
        # หาไฮไลท์จาก keywords
        keyword_highlights = detect_highlights_by_keywords(transcript, request.category)
        
        # หาไฮไลท์จากเสียง
        audio_highlights = detect_highlights_by_audio(request.video_path)
        
        return {
            "status": "success",
            "keyword_highlights": keyword_highlights[:request.max_highlights],
            "audio_highlights": audio_highlights[:request.max_highlights]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/subtitle")
async def add_subtitle(request: SubtitleRequest):
    """
    ใส่ซับไทเทิล
    
    Args:
    - video_path: ไฟล์วีดีโอ
    - style: สไตล์ซับ (normal, karaoke, tiktok)
    - language: ภาษา (th, en)
    """
    # จำลองการใส่ซับ
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status": "processing",
        "video_path": request.video_path,
        "style": request.style,
        "language": request.language
    }
    
    return {
        "status": "success",
        "job_id": job_id,
        "message": f"กำลังใส่ซับไทเทิลสไตล์ {request.style}"
    }


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """
    อัปโหลดไฟล์วีดีโอ
    
    Returns:
    - file_path: ไฟล์ที่อัปโหลด
    - file_id: รหัสไฟล์
    """
    file_id = str(uuid.uuid4())[:8]
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {
        "status": "success",
        "file_id": file_id,
        "file_path": file_path,
        "filename": file.filename
    }


@app.get("/api/projects")
async def list_projects():
    """รายชื่อโปรเจคทั้งหมด"""
    return {
        "projects": list(projects.values())
    }


@app.post("/api/projects")
async def create_project(name: str, description: str = ""):
    """สร้างโปรเจคใหม่"""
    project_id = str(uuid.uuid4())[:8]
    projects[project_id] = {
        "id": project_id,
        "name": name,
        "description": description,
        "files": [],
        "created_at": "2026-07-21"
    }
    return {"status": "success", "project_id": project_id}


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """ดึงสถานะงาน"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


@app.get("/api/health")
async def health_check():
    """ตรวจสอบสถานะระบบ"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "modules": {
            "ai_chat": True,
            "text_analyzer": True,
            "image_analyzer": True,
            "pipeline_manager": True
        }
    }


def _get_suggestions(intent: str) -> List[str]:
    """แนะนำคำสั่งตาม intent"""
    suggestions = {
        "analyze_video": [
            "หาไฮไลท์จากคลิปนี้",
            "ใส่ซับไทเทิลให้หน่อย",
            "ตัดช่วงที่น่าสนใจออกมา"
        ],
        "find_highlights": [
            "ตัดไฮไลท์ออกมาเป็นคลิป",
            "ใส่ซับไทเทิลลงบนไฮไลท์",
            "เพิ่มเอฟเฟกต์เสียง"
        ],
        "add_subtitle": [
            "เปลี่ยนสไตล์ซับเป็น karaoke",
            "เพิ่มภาษาอังกฤษ",
            "ปรับตำแหน่งซับ"
        ],
        "cut_clip": [
            "ตัดช่วง 30-60 วินาที",
            "ตัดเฉพาะไฮไลท์",
            "รวมหลายๆ คลิป"
        ],
        "add_effect": [
            "เพิ่มเพลงพื้นหลัง",
            "ใส่ transition",
            "เพิ่ม text overlay"
        ],
        "general": [
            "วิเคราะห์วีดีโอนี้",
            "หาไฮไลท์",
            "ใส่ซับไทเทิล"
        ]
    }
    return suggestions.get(intent, suggestions["general"])


# Mount static files (สำหรับ frontend)
if os.path.exists("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

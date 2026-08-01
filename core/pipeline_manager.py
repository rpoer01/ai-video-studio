"""
Pipeline Manager — จัดการ Workflow ทั้งหมด
"""

from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from dataclasses import dataclass
import time
import uuid


class PipelineStatus(Enum):
    """สถานะ Pipeline"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """สถานะ Step"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineStep:
    """ขั้นตอนใน Pipeline"""
    name: str
    func: Callable
    params: Dict[str, Any]
    status: StepStatus = StepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """ execute step"""
        self.status = StepStatus.RUNNING
        self.start_time = time.time()
        
        try:
            # รวม params กับ context
            merged_params = {**self.params, **context}
            self.result = self.func(**merged_params)
            self.status = StepStatus.COMPLETED
            self.end_time = time.time()
            return self.result
            
        except Exception as e:
            self.status = StepStatus.FAILED
            self.error = str(e)
            self.end_time = time.time()
            raise

    def get_duration(self) -> float:
        """ดึงเวลาที่ใช้"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0


@dataclass
class Pipeline:
    """Pipeline"""
    id: str
    name: str
    description: str
    steps: List[PipelineStep]
    status: PipelineStatus = PipelineStatus.PENDING
    context: Dict[str, Any] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    def __post_init__(self):
        if self.context is None:
            self.context = {}

    def execute(self) -> Dict[str, Any]:
        """ execute pipeline ทั้งหมด"""
        self.status = PipelineStatus.RUNNING
        self.start_time = time.time()
        
        try:
            for step in self.steps:
                print(f"Running step: {step.name}")
                result = step.execute(self.context)
                self.context.update(result)
            
            self.status = PipelineStatus.COMPLETED
            self.end_time = time.time()
            self.result = self.context
            return self.result
            
        except Exception as e:
            self.status = PipelineStatus.FAILED
            self.error = str(e)
            self.end_time = time.time()
            raise

    def get_duration(self) -> float:
        """ดึงเวลาที่ใช้"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0

    def get_step_results(self) -> List[Dict[str, Any]]:
        """ดึงผลลัพธ์ของแต่ละ step"""
        return [
            {
                "name": step.name,
                "status": step.status.value,
                "duration": step.get_duration(),
                "result": step.result
            }
            for step in self.steps
        ]


class PipelineManager:
    """
    Pipeline Manager
    
    ใช้สำหรับ:
    - สร้าง Pipeline ใหม่
    - execute Pipeline
    - จัดการ Pipeline หลายตัว
    """

    def __init__(self):
        self._pipelines: Dict[str, Pipeline] = {}

    def create_pipeline(self, 
                       name: str, 
                       description: str,
                       steps: List[Dict[str, Any]],
                       context: Optional[Dict[str, Any]] = None) -> Pipeline:
        """
        สร้าง Pipeline ใหม่
        
        Args:
            name: ชื่อ Pipeline
            description: คำอธิบาย
            steps: รายการ steps [{"name": "...", "func": callable, "params": {}}]
            context: ข้อมูลเริ่มต้น
            
        Returns:
            Pipeline object
        """
        pipeline_id = str(uuid.uuid4())[:8]
        
        pipeline_steps = [
            PipelineStep(
                name=step["name"],
                func=step["func"],
                params=step.get("params", {})
            )
            for step in steps
        ]
        
        pipeline = Pipeline(
            id=pipeline_id,
            name=name,
            description=description,
            steps=pipeline_steps,
            context=context or {}
        )
        
        self._pipelines[pipeline_id] = pipeline
        return pipeline

    def get_pipeline(self, pipeline_id: str) -> Optional[Pipeline]:
        """ดึง Pipeline ตาม ID"""
        return self._pipelines.get(pipeline_id)

    def execute_pipeline(self, pipeline_id: str) -> Dict[str, Any]:
        """ execute Pipeline"""
        pipeline = self.get_pipeline(pipeline_id)
        if not pipeline:
            raise ValueError(f"Pipeline not found: {pipeline_id}")
        return pipeline.execute()

    def list_pipelines(self) -> List[Dict[str, Any]]:
        """รายชื่อ Pipeline ทั้งหมด"""
        return [
            {
                "id": p.id,
                "name": p.name,
                "status": p.status.value,
                "duration": p.get_duration()
            }
            for p in self._pipelines.values()
        ]


# Global manager
manager = PipelineManager()


def create_video_analysis_pipeline(video_path: str) -> Pipeline:
    """
    สร้าง Pipeline สำหรับวิเคราะห์วีดีโอ
    
    Args:
        video_path: ไฟล์วีดีโอ
        
    Returns:
        Pipeline object
    """
    from analyzers.text_analyzer import TextAnalyzer
    from analyzers.image_analyzer import ImageAnalyzer
    from plugins.base import get_best_provider, ProviderType
    
    def extract_frames(video_path: str) -> Dict[str, Any]:
        """แยกเฟรมจากวีดีโอ"""
        # จำลองการแยกเฟรม
        return {"frames": [f"frame_{i}.jpg" for i in range(0, 60, 5)]}
    
    def transcribe_audio(video_path: str) -> Dict[str, Any]:
        """ถอดเสียง"""
        provider = get_best_provider(ProviderType.SPEECH_TO_TEXT)
        if provider:
            return provider.transcribe(video_path)
        return {"text": "", "segments": []}
    
    def analyze_text(segments: List[Dict]) -> Dict[str, Any]:
        """วิเคราะห์ข้อความ"""
        analyzer = TextAnalyzer()
        return analyzer.analyze(segments)
    
    def analyze_frames(frames: List[str]) -> Dict[str, Any]:
        """วิเคราะห์ภาพ"""
        analyzer = ImageAnalyzer()
        return {"analyses": [analyzer.analyze_frame(f) for f in frames]}
    
    def find_highlights(text_result: Dict, frame_result: Dict) -> Dict[str, Any]:
        """หาไฮไลท์"""
        # รวมผลวิเคราะห์
        return {
            "highlights": text_result.get("important_segments", []),
            "frame_highlights": frame_result.get("analyses", [])[:5]
        }
    
    steps = [
        {"name": "extract_frames", "func": extract_frames, "params": {"video_path": video_path}},
        {"name": "transcribe_audio", "func": transcribe_audio, "params": {"video_path": video_path}},
        {"name": "analyze_text", "func": analyze_text, "params": {}},
        {"name": "analyze_frames", "func": analyze_frames, "params": {}},
        {"name": "find_highlights", "func": find_highlights, "params": {}}
    ]
    
    return manager.create_pipeline(
        name="Video Analysis",
        description=f"วิเคราะห์วีดีโอ: {video_path}",
        steps=steps
    )


# ตัวอย่างการใช้งาน
if __name__ == "__main__":
    print("=== Pipeline Manager Demo ===\n")
    
    # ตัวอย่าง step functions
    def step1(x: int) -> Dict[str, Any]:
        return {"y": x * 2}
    
    def step2(y: int) -> Dict[str, Any]:
        return {"z": y + 10}
    
    def step3(z: int) -> Dict[str, Any]:
        return {"result": z ** 2}
    
    # สร้าง Pipeline
    pipeline = manager.create_pipeline(
        name="Simple Pipeline",
        description="ตัวอย่าง Pipeline ง่ายๆ",
        steps=[
            {"name": "step1", "func": step1, "params": {"x": 5}},
            {"name": "step2", "func": step2, "params": {}},
            {"name": "step3", "func": step3, "params": {}}
        ]
    )
    
    # Execute
    result = pipeline.execute()
    
    print(f"Pipeline ID: {pipeline.id}")
    print(f"Status: {pipeline.status.value}")
    print(f"Duration: {pipeline.get_duration():.2f}s")
    print(f"Result: {result}")
    
    print("\nStep Results:")
    for step_result in pipeline.get_step_results():
        print(f"  - {step_result['name']}: {step_result['status']} ({step_result['duration']:.2f}s)")

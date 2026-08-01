"""
Core — ระบบหลักของ AI Video Studio
"""

from .ai_chat import AIChatInterface
from .pipeline_manager import PipelineManager, Pipeline, create_video_analysis_pipeline

__all__ = [
    "AIChatInterface",
    "PipelineManager",
    "Pipeline",
    "create_video_analysis_pipeline"
]

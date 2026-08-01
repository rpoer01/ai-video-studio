"""
Base Plugin System — ระบบ Plugin สำหรับ AI Providers
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
import time


class ProviderType(Enum):
    """ประเภทของ AI Provider"""
    SPEECH_TO_TEXT = "speech_to_text"
    VISION = "vision"
    TEXT_GENERATION = "text_generation"
    AUDIO_ANALYSIS = "audio_analysis"
    VIDEO_ANALYSIS = "video_analysis"


@dataclass
class ProviderConfig:
    """ตั้งค่า Provider"""
    api_key: Optional[str] = None
    model: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    extra: Optional[Dict[str, Any]] = None


class AIProvider(ABC):
    """
    Abstract Base Class สำหรับ AI Provider
    
    ทุก Provider ต้อง implement:
    - provider_type: ประเภทของ Provider
    - name: ชื่อ Provider
    - transcribe(): ถอดเสียง (สำหรับ STT)
    - analyze_image(): วิเคราะห์ภาพ (สำหรับ Vision)
    - generate_text(): สร้างข้อความ (สำหรับ Text Gen)
    """

    def __init__(self, config: Optional[ProviderConfig] = None):
        self.config = config or ProviderConfig()
        self._usage_count = 0
        self._last_used = None

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """ประเภทของ Provider"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """ชื่อ Provider"""
        pass

    @abstractmethod
    def transcribe(self, audio_path: str, language: str = "th") -> Dict[str, Any]:
        """
        ถอดเสียง
        
        Args:
            audio_path: ไฟล์เสียง
            language: ภาษา
            
        Returns:
            transcript data
        """
        pass

    @abstractmethod
    def analyze_image(self, image_path: str, prompt: str = "") -> Dict[str, Any]:
        """
        วิเคราะห์ภาพ
        
        Args:
            image_path: ไฟล์ภาพ
            prompt: คำถาม/คำสั่ง
            
        Returns:
            analysis results
        """
        pass

    @abstractmethod
    def generate_text(self, prompt: str, context: Optional[str] = None) -> str:
        """
        สร้างข้อความ
        
        Args:
            prompt: คำถาม/คำสั่ง
            context: บริบทเพิ่มเติม
            
        Returns:
            generated text
        """
        pass

    def track_usage(self):
        """ติดตามการใช้งาน"""
        self._usage_count += 1
        self._last_used = time.time()

    def get_stats(self) -> Dict[str, Any]:
        """ดึงสถิติการใช้งาน"""
        return {
            "name": self.name,
            "type": self.provider_type.value,
            "usage_count": self._usage_count,
            "last_used": self._last_used
        }


class AIProviderRegistry:
    """
    คลัง AI Providers
    
    ใช้สำหรับ:
    - ลงทะเบียน Provider ใหม่
    - ค้นหา Provider ตามประเภท
    - เลือก Provider ที่เหมาะสม
    """

    def __init__(self):
        self._providers: Dict[str, AIProvider] = {}

    def register(self, provider: AIProvider):
        """ลงทะเบียน Provider"""
        self._providers[provider.name] = provider

    def get(self, name: str) -> Optional[AIProvider]:
        """ดึง Provider ตามชื่อ"""
        return self._providers.get(name)

    def get_by_type(self, provider_type: ProviderType) -> List[AIProvider]:
        """ดึง Provider ตามประเภท"""
        return [
            p for p in self._providers.values()
            if p.provider_type == provider_type
        ]

    def get_best_provider(self, provider_type: ProviderType) -> Optional[AIProvider]:
        """
        เลือก Provider ที่ดีที่สุดสำหรับงาน
        
        ปัจจัย:
        1. จำนวน usage (ใช้น้อย = 优先)
        2. API key มีหรือไม่
        """
        providers = self.get_by_type(provider_type)
        
        if not providers:
            return None
        
        # เรียงตาม usage count (น้อยที่สุดก่อน)
        return min(providers, key=lambda p: p._usage_count)

    def list_all(self) -> List[Dict[str, Any]]:
        """รายชื่อ Provider ทั้งหมด"""
        return [p.get_stats() for p in self._providers.values()]


# Global registry
registry = AIProviderRegistry()


def register_provider(provider: AIProvider):
    """ลงทะเบียน Provider (global)"""
    registry.register(provider)


def get_provider(name: str) -> Optional[AIProvider]:
    """ดึง Provider (global)"""
    return registry.get(name)


def get_best_provider(provider_type: ProviderType) -> Optional[AIProvider]:
    """เลือก Provider ที่ดีที่สุด (global)"""
    return registry.get_best_provider(provider_type)

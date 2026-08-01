"""
Image Analyzer — วิเคราะห์รูปภาพจากวีดีโอ
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import os


class MoodType(Enum):
    """ประเภทอารมณ์"""
    HAPPY = "happy"
    SAD = "sad"
    EXCITED = "excited"
    CALM = "calm"
    ANGRY = "angry"
    NEUTRAL = "neutral"


@dataclass
class DetectedObject:
    """วัตถุที่ตรวจพบ"""
    name: str
    confidence: float
    bbox: Optional[List[int]] = None  # [x, y, width, height]


@dataclass
class SceneInfo:
    """ข้อมูลฉาก"""
    scene_type: str  # indoor, outdoor, nature, urban, etc.
    mood: MoodType
    objects: List[DetectedObject]
    dominant_colors: List[str]
    brightness: float  # 0-1
    contrast: float  # 0-1


@dataclass
class FrameAnalysis:
    """ผลวิเคราะห์แต่ละเฟรม"""
    frame_number: int
    timestamp: float
    scene: SceneInfo
    text_detected: Optional[str] = None


class ImageAnalyzer:
    """
    วิเคราะห์รูปภาพจากวีดีโอ
    
    หน้าที่:
    1. ตรวจจับวัตถุ (Object Detection)
    2. จำแนกฉาก (Scene Classification)
    3. วิเคราะห์อารมณ์ (Mood Analysis)
    4. ตรวจจับข้อความในภาพ (OCR)
    5. วิเคราะห์สี (Color Analysis)
    """

    # จำแนกประเภทฉาก
    SCENE_TYPES = {
        "indoor": ["room", "office", "kitchen", "bedroom", "living room"],
        "outdoor": ["street", "park", "garden", "field", "mountain"],
        "nature": ["forest", "river", "ocean", "sky", "tree"],
        "urban": ["city", "building", "road", "car", "bridge"],
        "studio": ["studio", "stage", "screen", "background"]
    }

    def __init__(self, use_ai_vision: bool = True):
        """
        Args:
            use_ai_vision: ใช้ AI Vision (GPT-4V/Claude) หรือไม่
        """
        self.use_ai_vision = use_ai_vision

    def analyze_frame(self, frame_path: str) -> FrameAnalysis:
        """
        วิเคราะห์เฟรมเดียว
        
        Args:
            frame_path: ไฟล์ภาพ
            
        Returns:
            ผลวิเคราะห์
        """
        # วิเคราะห์ภาพ
        scene = self._analyze_scene(frame_path)
        text = self._detect_text(frame_path)
        
        return FrameAnalysis(
            frame_number=0,
            timestamp=0,
            scene=scene,
            text_detected=text
        )

    def analyze_video_frames(self, video_path: str, sample_rate: int = 1) -> List[FrameAnalysis]:
        """
        วิเคราะห์หลายๆ เฟรมจากวีดีโอ
        
        Args:
            video_path: ไฟล์วีดีโอ
            sample_rate: ทุกกี่วินาที采样
            
        Returns:
            รายการผลวิเคราะห์
        """
        # ในอนาคตจะ:
        # 1. ใช้ OpenCV แยกเฟรม
        # 2. วิเคราะห์แต่ละเฟรม
        # 3. รวมผลลัพธ์
        
        # จำลองผลลัพธ์
        return [
            FrameAnalysis(
                frame_number=i,
                timestamp=i * sample_rate,
                scene=SceneInfo(
                    scene_type="outdoor",
                    mood=MoodType.HAPPY,
                    objects=[],
                    dominant_colors=["blue", "green"],
                    brightness=0.7,
                    contrast=0.5
                )
            )
            for i in range(0, 60, sample_rate)
        ]

    def _analyze_scene(self, image_path: str) -> SceneInfo:
        """วิเคราะห์ฉาก"""
        if self.use_ai_vision:
            return self._analyze_with_ai(image_path)
        else:
            return self._analyze_locally(image_path)

    def _analyze_with_ai(self, image_path: str) -> SceneInfo:
        """
        วิเคราะห์ด้วย AI Vision
        
        ในอนาคตจะเชื่อมกับ:
        - OpenAI GPT-4V
        - Anthropic Claude
        - Google Gemini
        """
        # จำลองผลลัพธ์
        return SceneInfo(
            scene_type="outdoor",
            mood=MoodType.HAPPY,
            objects=[
                DetectedObject(name="person", confidence=0.95),
                DetectedObject(name="tree", confidence=0.88),
                DetectedObject(name="sky", confidence=0.92)
            ],
            dominant_colors=["blue", "green", "white"],
            brightness=0.75,
            contrast=0.55
        )

    def _analyze_locally(self, image_path: str) -> SceneInfo:
        """
        วิเคราะห์ท้องถิ่น (ไม่ใช้ AI)
        
        ใช้:
        - OpenCV สำหรับ edge detection, color analysis
        - PIL สำหรับ brightness, contrast
        """
        # จำลองผลลัพธ์
        return SceneInfo(
            scene_type="unknown",
            mood=MoodType.NEUTRAL,
            objects=[],
            dominant_colors=[],
            brightness=0.5,
            contrast=0.5
        )

    def _detect_text(self, image_path: str) -> Optional[str]:
        """
        ตรวจจับข้อความในภาพ (OCR)
        
        ใช้:
        - Tesseract OCR
        - EasyOCR
        - AI Vision
        """
        # จำลองผลลัพธ์
        return None

    def find_matching_scenes(self, 
                           video_frames: List[FrameAnalysis], 
                           target_mood: MoodType,
                           target_objects: Optional[List[str]] = None) -> List[FrameAnalysis]:
        """
        หาฉากที่ตรงกับอารมณ์/วัตถุที่ต้องการ
        
        Args:
            video_frames: ผลวิเคราะห์จากวีดีโอ
            target_mood: อารมณ์ที่ต้องการ
            target_objects: วัตถุที่ต้องการ
            
        Returns:
            รายการฉากที่ตรงกัน
        """
        matching = []
        
        for frame in video_frames:
            # ตรวจสอบอารมณ์
            if frame.scene.mood != target_mood:
                continue
            
            # ตรวจสอบวัตถุ
            if target_objects:
                frame_objects = [obj.name for obj in frame.scene.objects]
                if not any(obj in frame_objects for obj in target_objects):
                    continue
            
            matching.append(frame)
        
        return matching

    def match_with_text(self, 
                       frames: List[FrameAnalysis], 
                       text_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        จับคู่ภาพกับข้อความ
        
        Args:
            frames: ผลวิเคราะห์ภาพ
            text_segments: ข้อความที่ถอดได้
            
        Returns:
            รายการจับคู่ (frame + text + score)
        """
        matches = []
        
        for frame in frames:
            for text_seg in text_segments:
                # คำนวณความตรงกัน
                score = self._calculate_match_score(frame, text_seg)
                
                if score > 0.3:  # threshold
                    matches.append({
                        "frame": frame,
                        "text": text_seg,
                        "score": score
                    })
        
        return sorted(matches, key=lambda x: x['score'], reverse=True)

    def _calculate_match_score(self, frame: FrameAnalysis, text_seg: Dict[str, Any]) -> float:
        """
        คำนวณคะแนนความตรงกันระหว่างภาพกับข้อความ
        
        ปัจจัย:
        1. อารมณ์ของภาพ vs อารมณ์ของข้อความ
        2. วัตถุในภาพ vs คำในข้อความ
        3. สี/brightness vs อารมณ์
        """
        score = 0.0
        
        # ตรวจสอบอารมณ์
        text_mood = self._detect_text_mood(text_seg.get('text', ''))
        if frame.scene.mood == text_mood:
            score += 0.4
        
        # ตรวจสอบวัตถุ
        text_words = text_seg.get('text', '').lower().split()
        frame_objects = [obj.name.lower() for obj in frame.scene.objects]
        
        common = set(text_words) & set(frame_objects)
        if common:
            score += 0.3 * (len(common) / max(len(text_words), 1))
        
        # ตรวจสอบ brightness กับ อารมณ์
        if text_mood in [MoodType.HAPPY, MoodType.EXCITED]:
            if frame.scene.brightness > 0.6:
                score += 0.2
        elif text_mood == MoodType.SAD:
            if frame.scene.brightness < 0.4:
                score += 0.2
        
        return min(score, 1.0)

    def _detect_text_mood(self, text: str) -> MoodType:
        """ตรวจจับอารมณ์จากข้อความ"""
        positive_words = ["สุดยอด", "สวย", "ดี", "ชอบ", "รัก", "สนุก"]
        negative_words = ["แย่", "น่าเกลียด", "ผิดหวัง", "เสียใจ"]
        excitement_words = ["เดือด", "แตก", "ยับ", "โหด", "โคตร"]
        
        text_lower = text.lower()
        
        if any(w in text_lower for w in excitement_words):
            return MoodType.EXCITED
        elif any(w in text_lower for w in positive_words):
            return MoodType.HAPPY
        elif any(w in text_lower for w in negative_words):
            return MoodType.SAD
        
        return MoodType.NEUTRAL


# ตัวอย่างการใช้งาน
if __name__ == "__main__":
    # ทดสอบ Image Analyzer
    analyzer = ImageAnalyzer(use_ai_vision=True)
    
    print("=== Image Analyzer Demo ===\n")
    
    # วิเคราะห์เฟรมเดียว
    result = analyzer.analyze_frame("test_frame.jpg")
    print("ผลวิเคราะห์เฟรม:")
    print(f"  ฉาก: {result.scene.scene_type}")
    print(f"  อารมณ์: {result.scene.mood.value}")
    print(f"  วัตถุ: {[obj.name for obj in result.scene.objects]}")
    print(f"  สี主导: {result.scene.dominant_colors}")
    print(f"  ความสว่าง: {result.scene.brightness}")
    
    # ทดสอบจับคู่ภาพกับข้อความ
    frames = [
        FrameAnalysis(
            frame_number=0,
            timestamp=0,
            scene=SceneInfo(
                scene_type="outdoor",
                mood=MoodType.HAPPY,
                objects=[DetectedObject(name="person", confidence=0.9)],
                dominant_colors=["blue", "green"],
                brightness=0.7,
                contrast=0.5
            )
        )
    ]
    
    text_segments = [
        {"text": "วันนี้อากาศดีมาก ไปเที่ยวกัน", "start": 0, "end": 5}
    ]
    
    matches = analyzer.match_with_text(frames, text_segments)
    print(f"\nผลจับคู่ภาพ-ข้อความ:")
    for match in matches:
        print(f"  Score: {match['score']:.2f}")
        print(f"  Text: {match['text']['text']}")

"""
AI Chat Interface — ช่องทางสื่อสารกับ AI
สำหรับสั่งงานวิเคราะห์วีดีโอ/ข้อความ/รูปภาพ
"""

import json
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum


class MessageRole(Enum):
    """บทบาทของข้อความ"""
    USER = "user"
    AI = "ai"
    SYSTEM = "system"


@dataclass
class ChatMessage:
    """ข้อความในแชท"""
    role: MessageRole
    content: str
    timestamp: float
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['role'] = self.role.value
        return data


class AIChatInterface:
    """
    Chat Interface สำหรับสื่อสารกับ AI
    
    ใช้สำหรับ:
    - สั่งงานวิเคราะห์วีดีโอ
    - ถามคำถามเกี่ยวกับ content
    - ขอให้ทำ something กับ media
    
    ตัวอย่าง:
        chat = AIChatInterface()
        chat.send("ช่วยวิเคราะห์วีดีโอนี้ให้หน่อย")
        chat.send("หาไฮไลท์จากคลิปนี้")
        chat.send("ใส่ซับไทเทิลให้หน่อย")
    """

    def __init__(self, ai_provider: str = "openai"):
        """
        Args:
            ai_provider: ผู้ให้บริการ AI ที่ใช้ (openai/anthropic/google/local)
        """
        self.ai_provider = ai_provider
        self.messages: List[ChatMessage] = []
        self.context: Dict[str, Any] = {}
        
        # เพิ่ม system message เริ่มต้น
        self._add_system_message()

    def _add_system_message(self):
        """เพิ่มข้อความ system เริ่มต้น"""
        system_prompt = """คุณเป็น AI Video Editor Assistant ที่ช่วยจัดการวีดีโอ

หน้าที่ของคุณ:
1. วิเคราะห์วีดีโอ — หาฉาก, วัตถุ, อารมณ์, ข้อความ
2. หาไฮไลท์ — ช่วงที่น่าสนใจจากข้อความ/เสียง/ภาพ
3. ตัดคลิป — ตัดช่วงที่ต้องการ
4. ใส่ซับไทเทิล — สร้างซับจากข้อความที่ถอดได้
5. เพิ่มเอฟเฟกต์ — เสียง, transition, text overlay

ตอบสั้นๆ ชัดเจน เป็นภาษาไทย
ถ้าไม่เข้าใจให้ถามกลับ"""
        
        self.messages.append(ChatMessage(
            role=MessageRole.SYSTEM,
            content=system_prompt,
            timestamp=time.time()
        ))

    def send(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        ส่งข้อความไปหา AI
        
        Args:
            content: ข้อความที่ต้องการส่ง
            metadata: ข้อมูลเพิ่มเติม (เช่น file path, timestamp)
            
        Returns:
            คำตอบจาก AI
        """
        # เพิ่มข้อความ user
        user_msg = ChatMessage(
            role=MessageRole.USER,
            content=content,
            timestamp=time.time(),
            metadata=metadata
        )
        self.messages.append(user_msg)
        
        # จำลองการตอบจาก AI (ในอนาคตจะเชื่อมกับ AI จริง)
        ai_response = self._generate_response(content, metadata)
        
        # เพิ่มข้อความ AI
        ai_msg = ChatMessage(
            role=MessageRole.AI,
            content=ai_response,
            timestamp=time.time()
        )
        self.messages.append(ai_msg)
        
        return ai_response

    def _generate_response(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        สร้างคำตอบจาก AI (จำลอง)
        
        ในอนาคตจะเชื่อมกับ:
        - OpenAI API
        - Anthropic API
        - Google Gemini API
        - Local model
        """
        # วิเคราะห์ intent จากข้อความ
        intent = self._detect_intent(content)
        
        # สร้างคำตอบตาม intent
        if intent == "analyze_video":
            return self._handle_analyze_video(content, metadata)
        elif intent == "find_highlights":
            return self._handle_find_highlights(content, metadata)
        elif intent == "add_subtitle":
            return self._handle_add_subtitle(content, metadata)
        elif intent == "cut_clip":
            return self._handle_cut_clip(content, metadata)
        elif intent == "add_effect":
            return self._handle_add_effect(content, metadata)
        else:
            return self._handle_general(content, metadata)

    def _detect_intent(self, content: str) -> str:
        """ตรวจจับเจตนาจากข้อความ"""
        content_lower = content.lower()
        
        # วิเคราะห์วีดีโอ
        if any(word in content_lower for word in ["วิเคราะห์", "analyze", "ดู", "ดูแล้ว"]):
            return "analyze_video"
        
        # หาไฮไลท์
        if any(word in content_lower for word in ["ไฮไลท์", "highlight", "ช่วงสำคัญ", "น่าสนใจ"]):
            return "find_highlights"
        
        # ใส่ซับ
        if any(word in content_lower for word in ["ซับ", "subtitle", "คำบรรยาย", "ข้อความ"]):
            return "add_subtitle"
        
        # ตัดคลิป
        if any(word in content_lower for word in ["ตัด", "cut", "crop", "clips"]):
            return "cut_clip"
        
        # เพิ่มเอฟเฟกต์
        if any(word in content_lower for word in ["เอฟเฟกต์", "effect", "เสียง", "sound", "เพลง"]):
            return "add_effect"
        
        return "general"

    def _handle_analyze_video(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """จัดการคำสั่งวิเคราะห์วีดีโอ"""
        if metadata and 'video_path' in metadata:
            return f"กำลังวิเคราะห์วีดีโอ: {metadata['video_path']}\n\nจะวิเคราะห์:\n1. ฉาก (scenes)\n2. วัตถุ (objects)\n3. อารมณ์ (mood)\n4. ข้อความในภาพ (text)\n5. เสียง (audio)"
        return "กรุณาระบุไฟล์วีดีโอที่ต้องการวิเคราะห์ (ส่ง file path หรือ URL มาได้เลย)"

    def _handle_find_highlights(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """จัดการคำสั่งหาไฮไลท์"""
        if metadata and 'video_path' in metadata:
            return f"กำลังหาไฮไลท์จาก: {metadata['video_path']}\n\nจะวิเคราะห์จาก:\n1. ข้อความที่ถอดได้ (keywords)\n2. ระดับเสียง (audio peaks)\n3. การเคลื่อนไหวในภาพ (motion)\n4. อารมณ์ของฉาก (scene mood)"
        return "กรุณาระบุไฟล์วีดีโอที่ต้องการหาไฮไลท์"

    def _handle_add_subtitle(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """จัดการคำสั่งใส่ซับ"""
        return "กำลังเตรียมระบบใส่ซับไทเทิล\n\nรองรับ:\n1. ซับไทเทิลปกติ (SRT)\n2. ซับคาราโอเกะ (highlight คำ)\n3. ซับแบบ TikTok (มีสีสัน)\n\nกรุณาระบุประเภทซับที่ต้องการ"

    def _handle_cut_clip(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """จัดการคำสั่งตัดคลิป"""
        return "กำลังเตรียมเครื่องมือตัดคลิป\n\nรองรับ:\n1. ตัดตามช่วงเวลา (start-end)\n2. ตัดตามไฮไลท์ (auto)\n3. ตัดตามฉาก (scene-based)\n\nกรุณาระบุช่วงเวลาหรือโหมดที่ต้องการ"

    def _handle_add_effect(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """จัดการคำสั่งเพิ่มเอฟเฟกต์"""
        return "กำลังเตรียมเอฟเฟกต์\n\nรองรับ:\n1. เสียงเพลง (background music)\n2. Sound effects (rain, wind, etc.)\n3. Transition effects\n4. Text overlay\n5. Visual effects\n\nกรุณาระบุเอฟเฟกต์ที่ต้องการ"

    def _handle_general(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """จัดการคำสั่งทั่วไป"""
        return f"รับคำสั่งแล้ว: {content}\n\nฉันสามารถช่วยได้:\n- วิเคราะห์วีดีโอ\n- หาไฮไลท์\n- ตัดคลิป\n- ใส่ซับไทเทิล\n- เพิ่มเอฟเฟกต์\n\nลองสั่งดูได้เลย!"

    def get_history(self) -> List[Dict[str, Any]]:
        """ดึงประวัติแชท"""
        return [msg.to_dict() for msg in self.messages if msg.role != MessageRole.SYSTEM]

    def clear_history(self):
        """ล้างประวัติแชท"""
        self.messages = [self.messages[0]]  # เก็บ system message ไว้

    def set_context(self, key: str, value: Any):
        """ตั้งค่า context สำหรับแชท"""
        self.context[key] = value

    def get_context(self, key: str) -> Any:
        """ดึงค่า context"""
        return self.context.get(key)


# ตัวอย่างการใช้งาน
if __name__ == "__main__":
    # สร้าง chat interface
    chat = AIChatInterface()
    
    # ทดสอบส่งข้อความ
    print("=== AI Video Editor Chat ===\n")
    
    # วิเคราะห์วีดีโอ
    response = chat.send("ช่วยวิเคราะห์วีดีโอนี้ให้หน่อย", {"video_path": "test.mp4"})
    print(f"User: ช่วยวิเคราะห์วีดีโอนี้ให้หน่อย")
    print(f"AI: {response}\n")
    
    # หาไฮไลท์
    response = chat.send("หาไฮไลท์จากคลิปนี้", {"video_path": "test.mp4"})
    print(f"User: หาไฮไลท์จากคลิปนี้")
    print(f"AI: {response}\n")
    
    # ใส่ซับ
    response = chat.send("ใส่ซับไทเทิลให้หน่อย")
    print(f"User: ใส่ซับไทเทิลให้หน่อย")
    print(f"AI: {response}\n")
    
    # ตัดคลิป
    response = chat.send("ตัดช่วงวินาทีที่ 30-60 ออกมา")
    print(f"User: ตัดช่วงวินาทีที่ 30-60 ออกมา")
    print(f"AI: {response}\n")
    
    # ดูประวัติ
    print("=== ประวัติแชท ===")
    for msg in chat.get_history():
        print(f"[{msg['role']}] {msg['content'][:50]}...")

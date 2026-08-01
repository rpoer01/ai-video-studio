"""
OpenAI Provider — AI Provider สำหรับ OpenAI
"""

from typing import Dict, Any, Optional
from .base import AIProvider, ProviderType, ProviderConfig


class OpenAIProvider(AIProvider):
    """
    OpenAI Provider
    
    รองรับ:
    - GPT-4V (Vision)
    - GPT-4 (Text Generation)
    - Whisper (Speech-to-Text)
    """

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.VISION  # Primary type

    @property
    def name(self) -> str:
        return "openai"

    def __init__(self, config: Optional[ProviderConfig] = None):
        super().__init__(config)
        self._client = None

    def _get_client(self):
        """ดึง OpenAI client"""
        if self._client is None:
            try:
                import openai
                self._client = openai.OpenAI(api_key=self.config.api_key)
            except ImportError:
                raise ImportError("กรุณาติดตั้ง openai: pip install openai")
        return self._client

    def transcribe(self, audio_path: str, language: str = "th") -> Dict[str, Any]:
        """
        ถอดเสียงด้วย Whisper
        
        Args:
            audio_path: ไฟล์เสียง
            language: ภาษา
            
        Returns:
            transcript data
        """
        client = self._get_client()
        
        try:
            with open(audio_path, "rb") as audio_file:
                result = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    response_format="verbose_json"
                )
            
            self.track_usage()
            
            return {
                "text": result.text,
                "segments": [
                    {
                        "text": seg.text,
                        "start": seg.start,
                        "end": seg.end,
                        "confidence": seg.avg_logprob
                    }
                    for seg in result.segments
                ] if hasattr(result, 'segments') else [],
                "language": result.language
            }
            
        except Exception as e:
            return {"error": str(e)}

    def analyze_image(self, image_path: str, prompt: str = "") -> Dict[str, Any]:
        """
        วิเคราะห์ภาพด้วย GPT-4V
        
        Args:
            image_path: ไฟล์ภาพ
            prompt: คำถาม/คำสั่ง
            
        Returns:
            analysis results
        """
        client = self._get_client()
        
        if not prompt:
            prompt = "วิเคราะห์ภาพนี้ บอกว่ามีวัตถุอะไรบ้าง อารมณ์เป็นอย่างไร สี主导คือสีอะไร"

        try:
            import base64
            
            # อ่านไฟล์ภาพ
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # ตรวจสอบนามสกุลไฟล์
            ext = image_path.lower().split('.')[-1]
            mime_type = f"image/{'jpeg' if ext in ['jpg', 'jpeg'] else ext}"
            
            response = client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
            
            self.track_usage()
            
            return {
                "analysis": response.choices[0].message.content,
                "model": "gpt-4-vision-preview"
            }
            
        except Exception as e:
            return {"error": str(e)}

    def generate_text(self, prompt: str, context: Optional[str] = None) -> str:
        """
        สร้างข้อความด้วย GPT-4
        
        Args:
            prompt: คำถาม/คำสั่ง
            context: บริบทเพิ่มเติม
            
        Returns:
            generated text
        """
        client = self._get_client()
        
        messages = []
        if context:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = client.chat.completions.create(
                model=self.config.model or "gpt-4",
                messages=messages,
                max_tokens=2000
            )
            
            self.track_usage()
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Error: {str(e)}"

    def find_highlights(self, transcript: str, video_info: Optional[Dict] = None) -> Dict[str, Any]:
        """
        หาไฮไลท์จาก transcript ด้วย GPT-4
        
        Args:
            transcript: ข้อความที่ถอดได้
            video_info: ข้อมูลวีดีโอเพิ่มเติม
            
        Returns:
            highlight segments
        """
        context = """คุณเป็น AI Video Editor ที่เชี่ยวชาญในการหาไฮไลท์จากวีดีโอ

หน้าที่ของคุณ:
1. วิเคราะห์ transcript
2. หาช่วงที่น่าสนใจ (keywords, ความตื่นเต้น, อารมณ์)
3. แนะนำ timestamp สำหรับไฮไลท์

ตอบเป็น JSON format:
{
    "highlights": [
        {
            "start": 0,
            "end": 10,
            "reason": "เหตุผลที่เลือก",
            "score": 0.8
        }
    ]
}"""
        
        prompt = f"""วิเคราะห์ transcript นี้ หาไฮไลท์ที่น่าสนใจ:

Transcript:
{transcript}

{f'Video Info: {video_info}' if video_info else ''}

ให้แนะนำ 3-5 ช่วงที่เป็นไฮไลท์ พร้อม timestamp และเหตุผล"""
        
        result = self.generate_text(prompt, context)
        
        try:
            import json
            return json.loads(result)
        except:
            return {"highlights": [], "raw_response": result}

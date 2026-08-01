"""
Text Analyzer — วิเคราะห์ข้อความที่ถอดมาจากวีดีโอ
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import re


@dataclass
class TextSegment:
    """ช่วงข้อความ"""
    text: str
    start_time: float
    end_time: float
    confidence: float
    words: Optional[List[Dict[str, Any]]] = None


@dataclass
class KeywordMatch:
    """ผลการจับคู่คำสำคัญ"""
    keyword: str
    category: str
    segment: TextSegment
    score: float


class TextAnalyzer:
    """
    วิเคราะห์ข้อความที่ถอดมาจากวีดีโอ
    
    หน้าที่:
    1. หาคำสำคัญ (keywords) จาก transcript
    2. วิเคราะห์อารมณ์จากข้อความ
    3. จัดกลุ่มคำ (word grouping)
    4. หาความสัมพันธ์ระหว่างคำ
    """

    # คำสำคัญแยกตามหมวดหมู่
    KEYWORDS = {
        "emotion": {
            "positive": [
                "สุดยอด", "ดีมาก", "ว้าว", "โอ้โห", "สวย", "งาม", "ชอบ",
                "รัก", "มีความสุข", "ดีใจ", "สนุก", "น่ารัก", "เก่ง",
                "เยี่ยม", "ยอดเยี่ยม", "ประทับใจ", "ชื่นชม"
            ],
            "negative": [
                "แย่", "น่าเกลียด", "ผิดหวัง", "เสียใจ", "โกรธ", "เกลียด",
                "น่าเบื่อ", "ห่วย", "ไม่ชอบ", "ผิด", "พัง", "ล้มเหลว"
            ],
            "excitement": [
                "เดือด", "แตก", "ยับ", "คม", "โหด", "พีค", "โคตร",
                " Triple Kill", "Ace", "Monster Kill", "Wow", "OMG"
            ]
        },
        "category": {
            "gaming": [
                "แตก", "ยับ", "คม", "โหด", "kill", "die", "win",
                "lose", "level", "boss", "game", "play"
            ],
            "vlog": [
                "วันนี้", "เมื่อวาน", "พรุ่งนี้", "ไป", "มากิน",
                "เที่ยว", "เดินทาง", "สนุก", "สวย", "อร่อย"
            ],
            "review": [
                "น่าสนใจ", "แนะนำ", "ห้ามพลาด", "คุ้ม", "ไม่คุ้ม",
                "ดี", "ไม่ดี", "เปรียบเทียบ", "สรุป", "คะแนน"
            ],
            "business": [
                "สำคัญ", "วิเคราะห์", "เติบโต", "กำไร", "ขาดทุน",
                "ตลาด", "ลงทุน", "ยอดขาย", "เป้าหมาย"
            ]
        }
    }

    def __init__(self):
        """เริ่มต้น Text Analyzer"""
        self.segments: List[TextSegment] = []

    def analyze(self, transcript: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        วิเคราะห์ transcript ทั้งหมด
        
        Args:
            transcript: รายการ segments จาก AI transcription
            
        Returns:
            ผลการวิเคราะห์
        """
        # แปลงเป็น TextSegment objects
        self.segments = [
            TextSegment(
                text=seg.get('text', ''),
                start_time=seg.get('start', 0),
                end_time=seg.get('end', 0),
                confidence=seg.get('confidence', 0),
                words=seg.get('words', [])
            )
            for seg in transcript
        ]

        # วิเคราะห์แต่ละด้าน
        keywords_found = self._find_keywords()
        emotion_analysis = self._analyze_emotion()
        word_groups = self._group_words()
        important_segments = self._find_important_segments()

        return {
            "total_segments": len(self.segments),
            "total_duration": self._get_total_duration(),
            "keywords": keywords_found,
            "emotion": emotion_analysis,
            "word_groups": word_groups,
            "important_segments": important_segments
        }

    def _find_keywords(self) -> List[KeywordMatch]:
        """หาคำสำคัญจาก transcript"""
        matches = []
        
        for segment in self.segments:
            text = segment.text.lower()
            
            for category, subcategories in self.KEYWORDS.items():
                for subcat, keywords in subcategories.items():
                    for keyword in keywords:
                        if keyword.lower() in text:
                            matches.append(KeywordMatch(
                                keyword=keyword,
                                category=f"{category}/{subcat}",
                                segment=segment,
                                score=self._calculate_keyword_score(keyword, text)
                            ))
        
        return sorted(matches, key=lambda x: x.score, reverse=True)

    def _calculate_keyword_score(self, keyword: str, text: str) -> float:
        """คำนวณคะแนนของคำสำคัญ"""
        # ยิ่งคำอยู่ต้นข้อความ ยิ่งมีคะแนนสูง
        position = text.find(keyword.lower())
        length_score = len(keyword) / 10
        position_score = 1 - (position / max(len(text), 1))
        
        return (length_score + position_score) / 2

    def _analyze_emotion(self) -> Dict[str, Any]:
        """วิเคราะห์อารมณ์จากข้อความทั้งหมด"""
        all_text = " ".join([seg.text for seg in self.segments])
        
        # นับคำตามหมวดอารมณ์
        emotion_scores = {}
        for emotion, keywords in self.KEYWORDS["emotion"].items():
            count = sum(1 for kw in keywords if kw.lower() in all_text.lower())
            emotion_scores[emotion] = count
        
        # หาอารมณ์หลัก
        dominant_emotion = max(emotion_scores.items(), key=lambda x: x[1])[0] if emotion_scores else "neutral"
        
        return {
            "scores": emotion_scores,
            "dominant": dominant_emotion,
            "text_length": len(all_text)
        }

    def _group_words(self, max_words: int = 5) -> List[Dict[str, Any]]:
        """จัดกลุ่มคำสำหรับซับไทเทิล"""
        groups = []
        current_group = []
        current_start = 0
        
        for segment in self.segments:
            words = segment.words or []
            for word in words:
                if len(current_group) >= max_words:
                    # สร้าง group ใหม่
                    groups.append({
                        "text": " ".join([w['word'] for w in current_group]),
                        "start": current_start,
                        "end": current_group[-1].get('end', 0),
                        "word_count": len(current_group)
                    })
                    current_group = []
                
                current_group.append(word)
                if not current_start:
                    current_start = word.get('start', 0)
        
        # เพิ่ม group สุดท้าย
        if current_group:
            groups.append({
                "text": " ".join([w['word'] for w in current_group]),
                "start": current_start,
                "end": current_group[-1].get('end', 0),
                "word_count": len(current_group)
            })
        
        return groups

    def _find_important_segments(self, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """หาช่วงที่สำคัญ"""
        important = []
        
        for segment in self.segments:
            # คำนวณความสำคัญจาก keywords + ความยาว
            keywords_in_segment = self._find_keywords_in_text(segment.text)
            importance = len(keywords_in_segment) * 0.3 + min(len(segment.text) / 100, 1) * 0.7
            
            if importance >= threshold:
                important.append({
                    "text": segment.text,
                    "start": segment.start_time,
                    "end": segment.end_time,
                    "importance": importance,
                    "keywords": [kw.keyword for kw in keywords_in_segment]
                })
        
        return sorted(important, key=lambda x: x['importance'], reverse=True)

    def _find_keywords_in_text(self, text: str) -> List[KeywordMatch]:
        """หาคำสำคัญในข้อความ"""
        matches = []
        text_lower = text.lower()
        
        for category, subcategories in self.KEYWORDS.items():
            for subcat, keywords in subcategories.items():
                for keyword in keywords:
                    if keyword.lower() in text_lower:
                        matches.append(KeywordMatch(
                            keyword=keyword,
                            category=f"{category}/{subcat}",
                            segment=TextSegment(text=text, start_time=0, end_time=0, confidence=0),
                            score=1.0
                        ))
        
        return matches

    def _get_total_duration(self) -> float:
        """หาความยาวทั้งหมด"""
        if not self.segments:
            return 0
        return max(seg.end_time for seg in self.segments)

    def get_highlights(self, max_highlights: int = 5) -> List[Dict[str, Any]]:
        """
        หาไฮไลท์จาก transcript
        
        Returns:
            รายการไฮไลท์ที่เรียงตามคะแนน
        """
        important = self._find_important_segments()
        return important[:max_highlights]


# ตัวอย่างการใช้งาน
if __name__ == "__main__":
    # ทดสอบ Text Analyzer
    analyzer = TextAnalyzer()
    
    # จำลอง transcript
    sample_transcript = [
        {
            "text": "สวัสดีครับวันนี้เราจะมารีวิวเกมใหม่ที่สุดยอดมาก",
            "start": 0,
            "end": 5,
            "confidence": 0.95,
            "words": [
                {"word": "สวัสดี", "start": 0, "end": 0.5},
                {"word": "ครับ", "start": 0.5, "end": 1},
                {"word": "วันนี้", "start": 1, "end": 1.5},
                {"word": "เรา", "start": 1.5, "end": 2},
                {"word": "จะ", "start": 2, "end": 2.2},
                {"word": "มารีวิว", "start": 2.2, "end": 2.8},
                {"word": "เกม", "start": 2.8, "end": 3.2},
                {"word": "ใหม่", "start": 3.2, "end": 3.6},
                {"word": "ที่", "start": 3.6, "end": 3.8},
                {"word": "สุดยอด", "start": 3.8, "end": 4.3},
                {"word": "มาก", "start": 4.3, "end": 5}
            ]
        },
        {
            "text": "กราฟิกสวยมาก โหดมาก แตกยับเลย",
            "start": 5,
            "end": 10,
            "confidence": 0.92,
            "words": [
                {"word": "กราฟิก", "start": 5, "end": 5.5},
                {"word": "สวย", "start": 5.5, "end": 6},
                {"word": "มาก", "start": 6, "end": 6.3},
                {"word": "โหด", "start": 6.3, "end": 6.8},
                {"word": "มาก", "start": 6.8, "end": 7.1},
                {"word": "แตก", "start": 7.1, "end": 7.5},
                {"word": "ยับ", "start": 7.5, "end": 7.8},
                {"word": "เลย", "start": 7.8, "end": 10}
            ]
        }
    ]
    
    # วิเคราะห์
    result = analyzer.analyze(sample_transcript)
    
    print("=== ผลการวิเคราะห์ ===")
    print(f"จำนวน segments: {result['total_segments']}")
    print(f"ความยาวทั้งหมด: {result['total_duration']} วินาที")
    print(f"\nอารมณ์หลัก: {result['emotion']['dominant']}")
    print(f"คะแนนอารมณ์: {result['emotion']['scores']}")
    print(f"\nคำสำคัญที่พบ: {len(result['keywords'])} คำ")
    for kw in result['keywords'][:5]:
        print(f"  - {kw.keyword} ({kw.category}) คะแนน: {kw.score:.2f}")
    
    print(f"\nช่วงสำคัญ:")
    for seg in result['important_segments'][:3]:
        print(f"  - [{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text'][:50]}...")
        print(f"    คะแนน: {seg['importance']:.2f}, Keywords: {seg['keywords']}")

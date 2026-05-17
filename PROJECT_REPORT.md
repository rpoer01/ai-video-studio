# AI Video Studio: Auto Subtitle & Highlight Cutter (Thai Support)

โปรเจกต์นี้เป็นระบบตัดต่อวิดีโออัตโนมัติที่ใช้ AI ในการประมวลผลเสียง (Transcribe) เพื่อสร้างซับไทเทิลภาษาไทย และตรวจจับช่วงสำคัญ (Highlights) จากวิดีโอหรือ URL โดยอัตโนมัติ

---

## 🛠 เทคโนโลยีและโมดูลที่ใช้ (Core Modules)

1.  **OpenAI Whisper**: ใช้ในการถอดความเสียงเป็นข้อความ (Speech-to-Text) รองรับภาษาไทยได้แม่นยำสูง
2.  **MoviePy**: ใช้ในการจัดการไฟล์วิดีโอ ตัดต่อ (Subclip), รวมคลิป (Concatenate), และใส่ Text Overlay
3.  **yt-dlp**: ใช้ในการดาวน์โหลดวิดีโอจาก URL ต่างๆ เช่น YouTube, Facebook, TikTok
4.  **Flask**: ใช้สร้าง Web Interface สำหรับการใช้งานที่ง่ายผ่าน Browser
5.  **NumPy**: ใช้ในการประมวลผลสัญญาณเสียงเพื่อหา Audio Peaks (ช่วงที่มีเสียงดัง)
6.  **ImageMagick**: จำเป็นสำหรับ MoviePy ในการสร้าง TextClip (ซับไทเทิล)

---

## 📂 โครงสร้างไฟล์ (File Structure)

### 1. `main.py` (Web Application)
- เป็นจุดศูนย์กลางของระบบ (Entry Point)
- จัดการหน้าเว็บ UI และรับค่าจากผู้ใช้
- ทำหน้าที่ประสานงานระหว่างการสร้างซับไทเทิล (`render_subtitle_video`) และการตัดไฮไลท์

### 2. `highlight_engine.py` (The Core Engine)
- **`download_video(url)`**: จัดการดาวน์โหลดวิดีโอจากลิงก์
- **`detect_highlights_by_keywords(segments)`**: วิเคราะห์ข้อความจาก AI เพื่อหาคำสำคัญภาษาไทย เช่น "สุดยอด", "สวยงาม", "โหดมาก"
- **`detect_highlights_by_audio(video_path)`**: วิเคราะห์คลื่นเสียงเพื่อหาช่วงที่มีความตื่นเต้น (Peak Volume)
- **`merge_segments()`**: รวมช่วงเวลาที่ใกล้กันให้เป็นคลิปเดียว
- **`extract_highlights()`**: ทำการตัดและรวมวิดีโอออกมาเป็นไฟล์ใหม่

### 3. `process_highlights_cli.py` (Command Line Tool)
- เครื่องมือสำหรับสาย Dev หรือการทำ Automation
- สั่งงานผ่าน Terminal โดยไม่ต้องเปิดหน้าเว็บ

### 4. `process_video_cli.py` (Subtitle CLI)
- เครื่องมือสำหรับใส่ซับไทเทิลผ่าน Command Line

---

## 🚀 ฟีเจอร์เด่น (Key Features)

- **Thai Language Optimized**: มีชุดคำ Keyword ภาษาไทยที่ออกแบบมาเพื่อคลิปเกม, รีวิว, หรือการบรรยาย
- **Hybrid Highlight Detection**: ใช้ทั้ง "ความหมายของคำพูด" และ "ระดับเสียง" ร่วมกันเพื่อให้ได้ไฮไลท์ที่แม่นยำที่สุด
- **URL Processing**: ไม่ต้องโหลดวิดีโอลงเครื่องก่อน แค่ก๊อปปี้ลิงก์มาวาง ระบบจะจัดการให้หมด
- **Customizable UI**: สามารถลากวางตำแหน่งซับไทเทิลในหน้าเว็บพรีวิวได้

---

## 📝 วิธีการทำงานของระบบ (Workflow)

1. **Input**: รับไฟล์วิดีโอในเครื่อง หรือ URL จากอินเทอร์เน็ต
2. **AI Transcription**: ใช้ Whisper ถอดเสียงออกมาเป็นข้อความพร้อมระบุเวลา (Timestamp)
3. **Analysis**:
   - ค้นหาคำอุทานหรือคำชมในข้อความภาษาไทย
   - สแกนหาช่วงที่ระดับเสียงพุ่งสูงขึ้นกว่าค่าเฉลี่ย
4. **Execution**: นำช่วงเวลาที่ได้มาตัด (Crop) แล้วนำมาต่อกัน (Merge)
5. **Output**: ได้ไฟล์วิดีโอไฮไลท์ที่พร้อมใช้งานทันที

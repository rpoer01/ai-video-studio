# AI Video Studio Pro Editor

Editor ใหม่แบบ timeline-first แยกจาก `main.py` เดิม

## Run

```bash
python editor/server/app.py
```

เปิดที่:

```text
http://127.0.0.1:5001/editor
```

## MVP Features

- แยกระบบ editor เป็น `editor/server` และ `editor/web`
- Upload media เข้า media bin
- ลากวางไฟล์ลง timeline หลาย track
- รองรับ `video`, `image`, `audio`, `subtitle`, `effect`
- Move, trim, split, duplicate, group พื้นฐาน
- Lock / hide ระดับ track
- Inspector แก้ข้อความ, สี, ขนาด, ตำแหน่ง, opacity, animation
- Preview แบบ realtime สำหรับ video / image + subtitle overlay
- Auto subtitle จาก AssemblyAI ไปลง subtitle track
- Save / load project เป็น JSON
- Export MVP เป็นวิดีโอพร้อม text/subtitle overlay

## Main Files

- `editor/server/app.py` - Flask API และการเสิร์ฟหน้า editor
- `editor/server/services/render_service.py` - export/render timeline JSON
- `editor/web/index.html` - shell UI
- `editor/web/static/css/editor.css` - layout และ timeline styles
- `editor/web/static/js/app.js` - editor state และ actions
- `editor/web/static/js/timeline.js` - timeline rendering + interactions
- `editor/web/static/js/preview.js` - preview sync
- `editor/web/static/js/api.js` - เรียก backend API

## Notes

- Auto subtitle ใช้ `AssemblyAI` เหมือน pipeline เดิมของโปรเจค
- Export ตอนนี้เป็น MVP และเน้น compositing หลักสำหรับ video/image/audio/text/subtitle
- ฟีเจอร์ระดับ advanced เช่น transitions เชิงลึก, color grading จริงจัง, green screen, face tracking, AI enhance ยังต้องพัฒนาต่อบนฐาน editor นี้

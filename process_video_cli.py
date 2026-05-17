import os
import sys
import datetime
import glob
import shutil

# --- CRITICAL: Configure ImageMagick BEFORE importing MoviePy ---
def configure_imagemagick():
    # Try common paths for Windows
    common_paths = [
        r"C:\Program Files\ImageMagick-*\magick.exe",
        r"C:\Program Files (x86)\ImageMagick-*\magick.exe"
    ]
    for p in common_paths:
        matches = glob.glob(p)
        if matches:
            return matches[0]
    return None

magick_path = configure_imagemagick()
if magick_path:
    os.environ["IMAGEMAGICK_BINARY"] = magick_path
    print(f"Found ImageMagick at: {magick_path}")
else:
    print("Warning: ImageMagick (magick.exe) not found in standard paths.")

# Now we can import moviepy and whisper
import whisper
import imageio_ffmpeg
from moviepy import VideoFileClip, TextClip, CompositeVideoClip

# Ensure ffmpeg is in the PATH for Whisper
ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
ffmpeg_dir = os.path.dirname(ffmpeg_exe)
local_ffmpeg = os.path.join(ffmpeg_dir, "ffmpeg.exe")

if not os.path.exists(local_ffmpeg):
    try:
        shutil.copy(ffmpeg_exe, local_ffmpeg)
    except:
        pass

if ffmpeg_dir not in os.environ["PATH"]:
    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ["PATH"]

# Ensure UTF-8 output for Thai characters
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def format_timestamp(seconds: float):
    td = datetime.timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(td.microseconds / 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

def generate_srt(segments, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        for i, segment in enumerate(segments):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            text = segment['text'].strip()
            f.write(f"{i + 1}\n{start} --> {end}\n{text}\n\n")


def build_word_entries(segments):
    entries = []
    for seg in segments:
        words = seg.get("words") or []
        if words:
            for w in words:
                text = str(w.get("word", "")).strip()
                if not text:
                    continue
                start = float(w.get("start", seg["start"]))
                end = float(w.get("end", seg["end"]))
                if end - start < 0.03:
                    end = start + 0.03
                entries.append({"start": start, "end": end, "text": text})
        else:
            text = str(seg.get("text", "")).strip()
            if text:
                entries.append(
                    {
                        "start": float(seg["start"]),
                        "end": float(seg["end"]),
                        "text": text,
                    }
                )
    return entries

def log(msg):
    print(msg)
    sys.stdout.flush()

def process_video(video_path):
    log(f"--- กำลังเริ่มประมวลผลไฟล์: {video_path} ---")
    
    # 1. Load Whisper
    log("1. กำลังโหลด AI Model (Whisper base)...")
    model = whisper.load_model("base")
    
    # 2. Transcribe
    log("2. กำลังถอดเสียงจากวิดีโอ (Speech-to-Text)...")
    result = model.transcribe(video_path, fp16=False, word_timestamps=True, verbose=False)
    segments = result['segments']
    entries = build_word_entries(segments)
    
    if not entries:
        log("   ! ไม่พบเสียงพูดในคลิป (Whisper detected no speech)")
        entries = [{'start': 1.0, 'end': 5.0, 'text': '--- ทดสอบระบบซับไทเทิล ---'}]
    
    # 3. Generate SRT
    srt_path = os.path.splitext(video_path)[0] + ".srt"
    generate_srt(segments, srt_path)
    log(f"3. สร้างไฟล์ซับไทเทิลเสร็จแล้ว: {srt_path}")
    
    # 4. Burn-in Subtitles
    log("4. กำลังพยายามรวมซับไทเทิลเข้ากับวิดีโอ...")
    
    # Use User specified Kanit font path
    font_path = r"c:\Users\zazqi\Downloads\Kanit\Kanit-Black.ttf"
    if not os.path.exists(font_path):
        font_path = r"C:\Windows\Fonts\arial.ttf"
        
    log(f"   - ใช้ Font จากพาธ: {font_path}")
    
    try:
        if not os.environ.get("IMAGEMAGICK_BINARY"):
            log("   ! Warning: IMAGEMAGICK_BINARY not set.")
        else:
            log(f"   - ใช้ ImageMagick จาก: {os.environ['IMAGEMAGICK_BINARY']}")
            
        video = VideoFileClip(video_path)
        subtitle_clips = []
        
        # Always add a watermark/test subtitle at start so user can confirm subtitle is rendered
        test_clip = TextClip(
            text="AI AUTO SUBTITLE (TEST)",
            font=font_path,
            font_size=40,
            color="white",
            bg_color="black"
        ).with_start(0).with_duration(5.0).with_position(("center", "top"))
        subtitle_clips.append(test_clip)

        for segment in entries:
            txt = segment['text'].strip()
            if not txt: continue
            
            try:
                target_width = int(video.w * 0.9)
                txt_clip = TextClip(
                    text=txt, 
                    font=font_path, 
                    font_size=60,
                    color="yellow",
                    stroke_color="black", 
                    stroke_width=2,
                    method="caption",
                    size=(target_width, None),
                    bg_color="rgba(0,0,0,0.35)"
                ).with_start(segment["start"]).with_duration(segment["end"] - segment["start"]).with_position(("center", int(video.h * 0.78)))
                
                subtitle_clips.append(txt_clip)
            except Exception as te:
                log(f"   ! ไม่สามารถสร้าง TextClip ได้: {te}")
                break
        
        if subtitle_clips:
            final_video = CompositeVideoClip([video] + subtitle_clips)
            output_video = os.path.splitext(video_path)[0] + "_subtitled.mp4"
            log(f"   - กำลังเรนเดอร์วิดีโอใหม่ไปที่: {output_video}")
            # Use multiple threads to speed up rendering
            final_video.write_videofile(output_video, codec="libx264", audio_codec="aac", threads=4, fps=video.fps)
            log(f"--- เสร็จสมบูรณ์! ไฟล์วิดีโอพร้อมซับอยู่ที่: {output_video} ---")
        else:
            log("--- เสร็จสมบูรณ์เฉพาะไฟล์ซับ (.srt) เท่านั้น ---")
            
    except Exception as ve:
        log(f"   ! เกิดข้อผิดพลาดในการประมวลผลวิดีโอ: {ve}")

if __name__ == "__main__":
    target_video = r"c:\Users\zazqi\OneDrive\Desktop\wwwwaad\2026-04-04 23-16-28.mp4"
    if os.path.exists(target_video):
        process_video(target_video)
    else:
        print(f"ไม่พบไฟล์วิดีโอ: {target_video}")

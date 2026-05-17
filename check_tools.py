import os
import shutil
import subprocess
import imageio_ffmpeg
import glob

def check_ffmpeg():
    print("--- 1. ตรวจสอบ FFmpeg ---")
    # Check in PATH
    ffmpeg_in_path = shutil.which("ffmpeg")
    if ffmpeg_in_path:
        print(f"[OK] พบ FFmpeg ในระบบที่: {ffmpeg_in_path}")
    else:
        print("[!] ไม่พบ FFmpeg ในระบบ (PATH)")
    
    # Check via imageio_ffmpeg
    try:
        bundled_ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.exists(bundled_ffmpeg):
            print(f"[OK] พบ FFmpeg ที่มาพร้อมกับ Python ที่: {bundled_ffmpeg}")
        else:
            print("[!] ไม่พบ Bundled FFmpeg")
    except Exception as e:
        print(f"[!] เกิดข้อผิดพลาดขณะตรวจสอบ Bundled FFmpeg: {e}")

def check_imagemagick():
    print("\n--- 2. ตรวจสอบ ImageMagick ---")
    # Check in PATH
    magick_in_path = shutil.which("magick")
    if magick_in_path:
        print(f"[OK] พบ ImageMagick (magick) ในระบบที่: {magick_in_path}")
    else:
        convert_in_path = shutil.which("convert")
        if convert_in_path:
            print(f"[OK] พบ ImageMagick (convert) ในระบบที่: {convert_in_path}")
        else:
            print("[!] ไม่พบ ImageMagick ในระบบ (PATH)")
    
    # Check common installation paths on Windows
    common_paths = [
        r"C:\Program Files\ImageMagick-*\magick.exe",
        r"C:\Program Files (x86)\ImageMagick-*\magick.exe"
    ]
    found_any = False
    for p in common_paths:
        matches = glob.glob(p)
        for match in matches:
            print(f"[OK] พบไฟล์ติดตั้ง ImageMagick ที่: {match}")
            found_any = True
    
    if not found_any and not magick_in_path:
        print("[!] ไม่พบการติดตั้ง ImageMagick ในตำแหน่งมาตรฐาน")
        print("    -> แนะนำให้ดาวน์โหลดและติดตั้งจาก https://imagemagick.org/")
        print("    -> อย่าลืมติ๊กถูกที่ 'Install legacy utilities (e.g. convert)'")

def check_python_libs():
    print("\n--- 3. ตรวจสอบไลบรารี Python ---")
    libs = ["whisper", "moviepy", "imageio_ffmpeg", "PIL", "yt_dlp", "pythainlp", "cv2"]
    for lib in libs:
        try:
            __import__(lib if lib != "PIL" else "PIL.Image")
            print(f"[OK] ติดตั้งไลบรารี '{lib}' เรียบร้อยแล้ว")
        except ImportError:
            print(f"[!] ยังไม่ได้ติดตั้งไลบรารี '{lib}'")

if __name__ == "__main__":
    print("==========================================")
    print("ระบบตรวจสอบความพร้อมเครื่องมือ (Tool Checker)")
    print("==========================================\n")
    check_ffmpeg()
    check_imagemagick()
    check_python_libs()
    print("\n==========================================")

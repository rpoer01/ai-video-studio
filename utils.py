import os
import requests
import tkinter as tk
from tkinter import filedialog

FONTS = {
    "Kanit-Bold.ttf": [
        "https://github.com/google/fonts/raw/main/ofl/kanit/Kanit-Bold.ttf",
        "https://fonts.gstatic.com/s/kanit/v15/nKKf-Go6G5tXCR546Wv8X04.ttf"
    ],
    "Kanit-Regular.ttf": [
        "https://github.com/google/fonts/raw/main/ofl/kanit/Kanit-Regular.ttf",
        "https://fonts.gstatic.com/s/kanit/v15/nKKZ-Go6G5tXCR5uOQ.ttf"
    ],
    "Prompt-Bold.ttf": [
        "https://github.com/google/fonts/raw/main/ofl/prompt/Prompt-Bold.ttf",
        "https://fonts.gstatic.com/s/prompt/v10/-W6EbX-9Tg8Z2ZlU1Rhf.ttf"
    ]
}

def download_required_fonts(target_dir="fonts"):
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    
    paths = {}
    for name, urls in FONTS.items():
        path = os.path.join(target_dir, name)
        font_key = name.split('.')[0]
        
        if os.path.exists(path):
            paths[font_key] = os.path.abspath(path)
            continue
            
        success = False
        for url in urls:
            print(f"[*] Downloading font: {name} from {url}")
            try:
                r = requests.get(url, allow_redirects=True, timeout=10)
                if r.status_code == 200:
                    with open(path, 'wb') as f:
                        f.write(r.content)
                    paths[font_key] = os.path.abspath(path)
                    success = True
                    break
            except Exception as e:
                print(f"[!] Failed to download from {url}: {e}")
        
        if not success:
            print(f"[!!] Could not download {name}. Using Arial as fallback.")
            paths[font_key] = "Arial"
            
    return paths

def select_file_dialog():
    """Opens a native Windows file explorer to select a video file."""
    root = tk.Tk()
    root.withdraw()  # Hide the main tkinter window
    root.attributes("-topmost", True)  # Bring to front
    file_path = filedialog.askopenfilename(
        title="เลือกไฟล์วิดีโอ",
        filetypes=[("Video Files", "*.mp4 *.mkv *.avi *.mov *.flv *.wmv"), ("All Files", "*.*")]
    )
    root.destroy()
    return file_path

if __name__ == "__main__":
    download_required_fonts()

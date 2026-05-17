import os
import sys
import ai_models
import highlight_engine
import argparse
import shutil

# Ensure UTF-8 output for Thai characters
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description="AI Highlight Cutter with Thai Language Support")
    parser.add_argument("input", help="Video path or URL")
    parser.add_argument("--model", default="base", help="Whisper model (tiny, base, small, medium, large)")
    parser.add_argument("--audio-threshold", type=float, default=2.5, help="Audio peak threshold factor")
    parser.add_argument("--aspect-ratio", default="9:16", choices=["9:16", "16:9"], help="Output aspect ratio")
    parser.add_argument("--max-duration", type=float, default=60.0, help="Target highlight length in seconds")
    parser.add_argument("--category", default="Auto", choices=["Auto", "General", "Gaming", "Vlog/Review", "Business/News"], help="Keyword category")
    parser.add_argument("--output", help="Output video path")
    
    args = parser.parse_args()
    
    video_path = args.input
    
    # 1. Handle URL
    if video_path.startswith("http"):
        print(f"[*] Downloading video from URL: {video_path}")
        try:
            video_path = highlight_engine.download_video(video_path)
            print(f"[+] Downloaded: {video_path}")
        except Exception as e:
            print(f"[!] Error downloading video: {e}")
            return

    if not os.path.exists(video_path):
        print(f"[!] File not found: {video_path}")
        return

    # 2. Transcription
    print(f"[*] Loading Whisper model '{args.model}'...")
    model = ai_models.get_whisper_model(args.model)
    
    print("[*] Transcribing video for keyword detection...")
    result = model.transcribe(video_path, fp16=False)
    segments = result['segments']
    
    # 3. Detect Highlights
    print("[*] Detecting highlights by keywords...")
    kw_highlights = highlight_engine.detect_highlights_by_keywords(segments, category=args.category)
    
    print("[*] Detecting highlights by audio peaks...")
    audio_highlights = highlight_engine.detect_highlights_by_audio(video_path, threshold_factor=args.audio_threshold)
    
    # Combine and merge
    all_highlights = kw_highlights + audio_highlights
    with highlight_engine.VideoFileClip(video_path) as video:
        merged_highlights = highlight_engine.plan_highlight_segments(
            all_highlights,
            video.duration,
            target_duration=args.max_duration,
            transcript_segments=segments,
        )
        merged_highlights = highlight_engine.smooth_segments_to_transcript(
            merged_highlights,
            segments,
            video.duration,
            target_duration=args.max_duration,
        )
    
    if not merged_highlights:
        print("[!] No highlights detected.")
        return
    
    print(f"[+] Found {len(merged_highlights)} highlight segments:")
    for i, seg in enumerate(merged_highlights):
        print(f"  {i+1}. {seg['start']:.2f}s - {seg['end']:.2f}s | {seg['reason']}")
        
    # 4. Extract and Create Final Video
    print("[*] Creating highlight video...")
    output_path = highlight_engine.extract_highlights(
        video_path,
        merged_highlights,
        aspect_ratio=args.aspect_ratio,
        target_duration=None,
        audio_fade=0.22,
    )
    if output_path and args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
        shutil.move(output_path, args.output)
        output_path = args.output
    
    if output_path:
        print(f"[***] Highlight video created successfully: {output_path} [***]")
    else:
        print("[!] Failed to create highlight video.")

if __name__ == "__main__":
    main()

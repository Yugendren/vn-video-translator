#!/usr/bin/env python3
import os
import sys
import argparse
import json
from src.downloader import download_video, sanitize_filename
from src.ocr_engine import run_ocr
from src.segmenter import segment_raw_frames
from src.translator import translate_segments
from src.renderer import render_overlays_and_video, export_subtitles

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(ROOT_DIR, "config", "default.json")
DEFAULT_OUTPUT_DIR = os.path.join(ROOT_DIR, "output")

def load_config(config_path):
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def process_single_video(video_path, title, output_dir, config, api_key=None):
    safe_title = sanitize_filename(title)[:50]
    work_dir = os.path.join(output_dir, f"work_{safe_title}")
    os.makedirs(work_dir, exist_ok=True)
    
    raw_ocr_json = os.path.join(work_dir, "raw_ocr.json")
    cleaned_segments_json = os.path.join(work_dir, "segments.json")
    translated_json = os.path.join(work_dir, "translated.json")
    
    out_video_path = os.path.join(output_dir, f"{safe_title}_English_Subbed.mp4")
    out_srt_path = os.path.join(output_dir, f"{safe_title}_English.srt")
    
    print("\n" + "=" * 60)
    print(f"🎬 Processing: {title}")
    print("=" * 60)
    
    # 1. OCR scanning
    if not os.path.exists(raw_ocr_json):
        run_ocr(
            video_path=video_path,
            output_json=raw_ocr_json,
            interval=config.get("sample_interval", 1.0),
            crop_y=config.get("crop_y_ratio", 0.72),
            crop_h=config.get("crop_h_ratio", 0.28),
            langs=",".join(config.get("ocr_languages", ["zh-Hans", "en-US"]))
        )
    else:
        print(f"⏩ Found existing OCR data at {raw_ocr_json}, skipping scan.")
        
    # 2. Dialogue segmentation
    if not os.path.exists(cleaned_segments_json):
        segments = segment_raw_frames(raw_ocr_json, cleaned_segments_json)
    else:
        print(f"⏩ Found existing dialogue segments at {cleaned_segments_json}.")
        with open(cleaned_segments_json, "r", encoding="utf-8") as f:
            segments = json.load(f)
            
    # 3. Translation
    if not os.path.exists(translated_json):
        translated = translate_segments(
            segments=segments,
            api_key=api_key,
            game_context=config.get("game_context", "Visual Novel"),
            target_lang=config.get("target_language", "English")
        )
        with open(translated_json, "w", encoding="utf-8") as f:
            json.dump(translated, f, ensure_ascii=False, indent=2)
    else:
        print(f"⏩ Found existing translations at {translated_json}.")
        with open(translated_json, "r", encoding="utf-8") as f:
            translated = json.load(f)
            
    # 4. Subtitle Export
    export_subtitles(translated, out_srt_path)
    
    # 5. Overlay and Hardware-Accelerated Video Rendering
    render_overlays_and_video(
        video_path=video_path,
        segments=translated,
        output_video_path=out_video_path,
        config=config,
        work_dir=work_dir
    )
    
    print(f"\n✨ Completed! Subbed video: {out_video_path}\n")
    return out_video_path

def read_links_file(filepath):
    urls = []
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
    return urls

def main():
    parser = argparse.ArgumentParser(description="Automated VN Video Translator & Localizer")
    parser.add_argument("input", nargs="?", help="URL or path to links.txt or video file")
    parser.add_argument("--links", help="Path to links file", default="links.txt")
    parser.add_argument("--add-link", help="Append a URL to links.txt and run")
    parser.add_argument("--config", help="Path to configuration JSON", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output", help="Output directory", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--api-key", help="Gemini API Key")
    parser.add_argument("--target-lang", help="Target language (e.g. English, Vietnamese)")
    parser.add_argument("--game", help="Game name / context description")
    
    args = parser.parse_args()
    config = load_config(args.config)
    
    if args.target_lang:
        config["target_language"] = args.target_lang
    if args.game:
        config["game_context"] = args.game
        
    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)
    
    api_key = args.api_key or os.environ.get("GEMINI_API_KEY")
    
    # Check if adding link
    if args.add_link:
        with open(args.links, "a", encoding="utf-8") as f:
            f.write(f"\n{args.add_link.strip()}\n")
        print(f"➕ Added {args.add_link} to {args.links}")
        
    urls_to_process = []
    
    # If positional input provided
    if args.input:
        if args.input.startswith("http://") or args.input.startswith("https://"):
            urls_to_process.append(args.input)
        elif os.path.isfile(args.input):
            if args.input.endswith(".txt"):
                urls_to_process.extend(read_links_file(args.input))
            elif args.input.endswith((".mp4", ".mkv", ".mov", ".webm")):
                # Local video file directly
                title = os.path.splitext(os.path.basename(args.input))[0]
                process_single_video(args.input, title, output_dir, config, api_key)
                return
        else:
            urls_to_process.extend(read_links_file(args.input))
    else:
        # Default to reading links.txt
        urls_to_process.extend(read_links_file(args.links))
        
    if not urls_to_process:
        print("ℹ️ No links found in links.txt or command line.")
        user_url = input("Enter a video URL to process (or paste links into links.txt): ").strip()
        if user_url:
            urls_to_process.append(user_url)
        else:
            print("Exiting.")
            return
            
    print(f"📋 Found {len(urls_to_process)} video URL(s) to process.")
    for idx, url in enumerate(urls_to_process):
        print(f"\n▶ [{idx + 1}/{len(urls_to_process)}] Downloading and processing: {url}")
        downloads_dir = os.path.join(output_dir, "downloads")
        video_path, title = download_video(url, downloads_dir)
        process_single_video(video_path, title, output_dir, config, api_key)

if __name__ == "__main__":
    main()
EOF
chmod +x /Users/yugendren/projects/vn-video-translator/translate.py

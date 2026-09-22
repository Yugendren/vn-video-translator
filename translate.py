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
from src.lore_manager import LoreManager

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(ROOT_DIR, "config", "default.json")
DEFAULT_OUTPUT_DIR = os.path.join(ROOT_DIR, "output")

ABOUT_TEXT = """
================================================================================
   VN Video Translator & Localizer - Overview & Quick Guide
================================================================================

WHAT THIS TOOL DOES:
  Automatically transforms raw visual novel & anime game cutscene videos into
  fully localized, hardcoded subbed 1080p videos with companion .srt files.

  1. Downloads videos at 1080p from Bilibili or YouTube (or takes local files).
  2. Apple Vision OCR on Apple Silicon Neural Engine extracts dialogue & timestamps (~15x speed).
  3. De-duplicates typewriter animations into contiguous, stabilized dialogue sentences.
  4. Translates into English using either Gemini Flash (Option 1) or Local Qwen (Option 2).
  5. Dynamically auto-fits text into the dialogue box (auto-shrinks long lines to prevent collision).
  6. Burns translucent UI banners over the original text via Apple M4 GPU acceleration (200+ FPS).

--------------------------------------------------------------------------------
WHICH ENGINE TO CHOOSE? (Option 1 vs Option 2)
--------------------------------------------------------------------------------
  Option 1: Gemini Flash (Recommended for Story Quality)
    * When to use: You want studio-level localization, nuanced character personalities
      (teasing, formal maid, childish, mystical prophecies), and deep lore awareness.
    * Cost: ~$0.001 per 30-minute episode (less than 1/10th of a cent).
    * Speed: ~3 to 5 seconds for the entire episode.
    * Setup: Free API key from Google AI Studio:
      https://aistudio.google.com/app/apikey
      If not already set in .env, the CLI interactively prompts and auto-saves it for you.

  Option 2: Local Model (Recommended for Offline / Bulk Processing)
    * When to use: You want 100% free, 100% offline translation with zero API keys or accounts.
    * Cost: $0.00 (completely free & private).
    * Speed: ~45 seconds on Apple Silicon Metal GPU (Qwen 2.5 3B/7B).
    * Setup: Zero manual configuration needed. The CLI automatically checks for llama.cpp
      (offering one-click brew install) and auto-downloads Qwen 2.5 3B if no model is found.

--------------------------------------------------------------------------------
BEST PRACTICES & TIPS:
--------------------------------------------------------------------------------
  * Typography:
      --font latex   (Default: STIX Two Text / TeX book serif, looks stunning)
      --font arial   (Modern, clean sans-serif)
      --font times   (Classic serif)
  * Text Fitting:
      The font stays fixed at 28pt by default. If a line is exceptionally long,
      it automatically steps down to 24pt/20pt/16pt to ensure zero word collision
      or clipping. You can configure --font-size and --min-font-size.
  * Lore & Context:
      Pass --lore gfl2 (or --lore lore/my_vn.json) to enforce canonical names.
      Pass --context "Scene description" to provide background hints.
      Edit config/prompt_template.txt to change the base system prompt directly.

--------------------------------------------------------------------------------
QUICK COMMANDS:
--------------------------------------------------------------------------------
  Batch run from links.txt:    ./run.sh
  Single link (Option 1):      ./run.sh "https://..." --engine 1 --lore gfl2
  Single link (Option 2):      ./run.sh "https://..." --engine 2 --font latex
  Append link & run:           ./run.sh --add-link "https://..."
  Local video file:            ./run.sh /path/to/video.mp4
================================================================================
"""

def load_config(config_path):
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def process_single_video(video_path, title, output_dir, config, lore_mgr, engine="auto", api_key=None, model_path=None):
    safe_title = sanitize_filename(title)[:50]
    work_dir = os.path.join(output_dir, f"work_{safe_title}")
    os.makedirs(work_dir, exist_ok=True)
    
    raw_ocr_json = os.path.join(work_dir, "raw_ocr.json")
    cleaned_segments_json = os.path.join(work_dir, "segments.json")
    translated_json = os.path.join(work_dir, "translated.json")
    
    out_video_path = os.path.join(output_dir, f"{safe_title}_English_Subbed.mp4")
    out_srt_path = os.path.join(output_dir, f"{safe_title}_English.srt")
    
    print("\n" + "=" * 60)
    print(f"[PROCESS] Video: {title}")
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
        print(f"[CACHE] Found existing OCR data at {raw_ocr_json}, skipping scan.")
        
    # 2. Dialogue segmentation
    if not os.path.exists(cleaned_segments_json):
        segments = segment_raw_frames(raw_ocr_json, cleaned_segments_json)
    else:
        print(f"[CACHE] Found existing dialogue segments at {cleaned_segments_json}.")
        with open(cleaned_segments_json, "r", encoding="utf-8") as f:
            segments = json.load(f)
            
    # 3. Translation (Option 1 or Option 2)
    if not os.path.exists(translated_json):
        translated = translate_segments(
            segments=segments,
            engine=engine,
            api_key=api_key,
            lore_manager=lore_mgr,
            model_path=model_path,
            target_lang=config.get("target_language", "English")
        )
        with open(translated_json, "w", encoding="utf-8") as f:
            json.dump(translated, f, ensure_ascii=False, indent=2)
    else:
        print(f"[CACHE] Found existing translations at {translated_json}.")
        with open(translated_json, "r", encoding="utf-8") as f:
            translated = json.load(f)
            
    # 4. Subtitle Export
    export_subtitles(translated, out_srt_path)
    
    # 5. Dynamic Overlay and Hardware-Accelerated Video Rendering
    render_overlays_and_video(
        video_path=video_path,
        segments=translated,
        output_video_path=out_video_path,
        config=config,
        work_dir=work_dir
    )
    
    print(f"\n[SUCCESS] Completed. Output video: {out_video_path}\n")
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
    if "--about" in sys.argv:
        print(ABOUT_TEXT)
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="Automated VN Video Translator & Localizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ./run.sh links.txt
  ./run.sh "https://www.bilibili.com/video/BV1sbhk6GEtY?p=1" --engine 1 --lore gfl2
  ./run.sh "https://www.bilibili.com/video/BV1sbhk6GEtY?p=1" --engine 2 --font latex
  ./run.sh --add-link "https://www.bilibili.com/video/BV..."
  ./run.sh --about

Use --about for a quick explanation of Option 1 vs Option 2 and best practices.
"""
    )
    
    parser.add_argument("input", nargs="?", help="Video URL, path to links.txt, or local video file (.mp4)")
    parser.add_argument("--about", action="store_true", help="Show quick guide on how it works & Option 1 vs 2")
    parser.add_argument("--links", help="Path to links file (default: links.txt)", default="links.txt")
    parser.add_argument("--add-link", help="Append a URL to links.txt and immediately run")
    parser.add_argument("--engine", choices=["auto", "1", "2", "gemini", "local"], default="auto",
                        help="Translation engine: [1/gemini] = Gemini Flash, [2/local] = Local Qwen model")
    parser.add_argument("--api-key", help="Gemini API Key (Option 1)")
    parser.add_argument("--model-path", help="Path to local .gguf model (Option 2)")
    parser.add_argument("--font", default="latex", help="Subtitle font: latex, arial, times, or path to .ttf (default: latex)")
    parser.add_argument("--font-size", type=int, default=28, help="Base dialogue font size in pt (default: 28)")
    parser.add_argument("--min-font-size", type=int, default=16, help="Minimum font size for auto-fitting long lines (default: 16)")
    parser.add_argument("--lore", help="Lore preset or path to lore JSON (e.g. gfl2, genshin, or lore/custom.json)")
    parser.add_argument("--context", help="One-off scene context or background notes for the translator")
    parser.add_argument("--target-lang", help="Target language (default: English)")
    parser.add_argument("--config", help="Path to configuration JSON (default: config/default.json)", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output", help="Output directory (default: output/)", default=DEFAULT_OUTPUT_DIR)
    
    args = parser.parse_args()
    config = load_config(args.config)
    
    # Overrides from CLI
    if args.font:
        config["font"] = args.font
    if args.font_size:
        config["font_size"] = args.font_size
    if args.min_font_size:
        config["min_font_size"] = args.min_font_size
    if args.target_lang:
        config["target_language"] = args.target_lang
        
    lore_mgr = LoreManager(lore_path=args.lore, scene_context=args.context)
    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)
    
    # Check if adding link
    if args.add_link:
        with open(args.links, "a", encoding="utf-8") as f:
            f.write(f"\n{args.add_link.strip()}\n")
        print(f"[CONFIG] Added {args.add_link} to {args.links}")
        
    urls_to_process = []
    
    # Positional input handling
    if args.input:
        if args.input.startswith("http://") or args.input.startswith("https://"):
            urls_to_process.append(args.input)
        elif os.path.isfile(args.input):
            if args.input.endswith(".txt"):
                urls_to_process.extend(read_links_file(args.input))
            elif args.input.endswith((".mp4", ".mkv", ".mov", ".webm")):
                title = os.path.splitext(os.path.basename(args.input))[0]
                process_single_video(args.input, title, output_dir, config, lore_mgr, args.engine, args.api_key, args.model_path)
                return
        else:
            urls_to_process.extend(read_links_file(args.input))
    else:
        urls_to_process.extend(read_links_file(args.links))
        
    if not urls_to_process:
        print("[INFO] No links found in links.txt or command line.")
        user_url = input("Enter a video URL to process (or press Enter to exit): ").strip()
        if user_url:
            urls_to_process.append(user_url)
        else:
            print("Exiting.")
            return
            
    print(f"[INFO] Found {len(urls_to_process)} video URL(s) to process.")
    for idx, url in enumerate(urls_to_process):
        print(f"\n[{idx + 1}/{len(urls_to_process)}] Downloading and processing: {url}")
        downloads_dir = os.path.join(output_dir, "downloads")
        video_path, title = download_video(url, downloads_dir)
        process_single_video(video_path, title, output_dir, config, lore_mgr, args.engine, args.api_key, args.model_path)

if __name__ == "__main__":
    main()

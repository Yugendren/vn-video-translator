import os
import sys
import json
import textwrap
import subprocess
from PIL import Image, ImageDraw, ImageFont
from .glossary import resolve_speaker

def format_srt_time(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def export_subtitles(segments, srt_path):
    with open(srt_path, "w", encoding="utf-8") as f:
        for idx, seg in enumerate(segments):
            text = seg.get("en_text", seg.get("text", ""))
            spk = resolve_speaker(seg.get("speaker"))
            start_str = format_srt_time(seg["start"])
            end_str = format_srt_time(seg["end"])
            f.write(f"{idx + 1}\n")
            f.write(f"{start_str} --> {end_str}\n")
            if spk:
                f.write(f"<b>[{spk}]</b> {text}\n\n")
            else:
                f.write(f"{text}\n\n")
    print(f"📝 Subtitles exported to: {srt_path}")

def render_overlays_and_video(
    video_path,
    segments,
    output_video_path,
    config,
    work_dir
):
    overlays_dir = os.path.join(work_dir, "overlays")
    os.makedirs(overlays_dir, exist_ok=True)
    
    # 1. Blank transparent background
    blank = Image.new('RGBA', (1920, 1080), (0, 0, 0, 0))
    blank.save(os.path.join(overlays_dir, "blank.png"))
    
    # Fonts
    font_speaker_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    font_text_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
    
    spk_font = ImageFont.truetype(font_speaker_path, config.get("speaker_font_size", 30))
    txt_font = ImageFont.truetype(font_text_path, config.get("dialogue_font_size", 27))
    
    box_rect = config.get("box_rect_1080p", [78, 825, 1842, 1047])
    box_color = tuple(config.get("box_color", [14, 24, 27, 248]))
    
    print(f"🎨 Generating {len(segments)} dialogue overlay textures...")
    for idx, seg in enumerate(segments):
        text = seg.get("en_text", seg.get("text", ""))
        spk = resolve_speaker(seg.get("speaker"))
        
        img = blank.copy()
        draw = ImageDraw.Draw(img)
        
        # Dark rounded box matching game dialogue UI
        draw.rounded_rectangle(box_rect, radius=10, fill=box_color)
        
        # Text wrapping
        wrapped_lines = textwrap.wrap(text, width=86)
        wrapped_text = "\n".join(wrapped_lines)
        
        if spk:
            draw.text((112, 846), f"|||| {spk}", fill=(255, 255, 255, 255), font=spk_font)
            draw.text((112, 894), wrapped_text, fill=(240, 245, 250, 255), font=txt_font, spacing=7)
        else:
            draw.text((112, 868), wrapped_text, fill=(235, 242, 248, 255), font=txt_font, spacing=8)
            
        img.save(os.path.join(overlays_dir, f"seg_{idx:03d}.png"))
        
    # 2. Concat script
    concat_path = os.path.join(work_dir, "concat.txt")
    
    # Get video duration via ffprobe
    probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
    res = subprocess.run(probe_cmd, capture_output=True, text=True)
    total_duration = float(res.stdout.strip()) if res.returncode == 0 else 3600.0
    
    current_time = 0.0
    with open(concat_path, "w", encoding="utf-8") as f:
        f.write("ffconcat version 1.0\n")
        for idx, seg in enumerate(segments):
            s_start = max(seg["start"], current_time)
            s_end = max(seg["end"], s_start + 0.5)
            
            if s_start > current_time:
                f.write(f"file 'overlays/blank.png'\n")
                f.write(f"duration {s_start - current_time:.3f}\n")
                current_time = s_start
                
            f.write(f"file 'overlays/seg_{idx:03d}.png'\n")
            f.write(f"duration {s_end - current_time:.3f}\n")
            current_time = s_end
            
        if current_time < total_duration:
            f.write(f"file 'overlays/blank.png'\n")
            f.write(f"duration {total_duration - current_time:.3f}\n")
        f.write("file 'overlays/blank.png'\n")
        
    # 3. Hardware accelerated rendering with FFmpeg
    # Check if videotoolbox is available
    check_enc = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True)
    use_videotoolbox = "h264_videotoolbox" in check_enc.stdout
    vcodec = "h264_videotoolbox" if use_videotoolbox else "libx264"
    bitrate = config.get("video_bitrate", "4500k")
    
    print(f"🎬 Burning overlays into video using {vcodec} hardware acceleration...")
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-f", "concat", "-safe", "0", "-i", concat_path,
        "-filter_complex", "[0:v][1:v]overlay=0:0:shortest=1",
        "-c:v", vcodec,
        "-b:v", bitrate,
        "-c:a", "copy",
        output_video_path
    ]
    
    proc = subprocess.Popen(ffmpeg_cmd, stderr=subprocess.PIPE, text=True)
    for line in proc.stderr:
        if "frame=" in line or "speed=" in line:
            print(f"\r  {line.strip()}", end="", flush=True)
    proc.wait()
    print()
    
    if proc.returncode != 0:
        raise RuntimeError("FFmpeg rendering failed.")
        
    print(f"🎉 Final translated video created at: {output_video_path}")
    return output_video_path

import os
import subprocess
import json
import re

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>| ]', '_', name)

def get_video_info(url):
    cmd = ["yt-dlp", "--dump-json", "--no-playlist", url]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        try:
            data = json.loads(res.stdout)
            return {
                "title": data.get("title", "video"),
                "duration": data.get("duration", 0),
                "id": data.get("id", "vid")
            }
        except Exception:
            pass
    return {"title": "video", "duration": 0, "id": "vid"}

def download_video(url, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    info = get_video_info(url)
    clean_title = sanitize_filename(info["title"])[:50]
    out_template = os.path.join(output_dir, f"{clean_title}_raw.%(ext)s")
    
    print(f"[DOWNLOAD] Fetching video: {info['title']}...")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f", "30080+30280/30064+30280/bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "-o", out_template,
        url
    ]
    
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout:
        if "%" in line or "ETA" in line or "Destination" in line:
            print(f"\r  {line.strip()}", end="", flush=True)
    proc.wait()
    print()
    
    if proc.returncode != 0:
        raise RuntimeError(f"Download failed for {url}")
        
    expected_path = os.path.join(output_dir, f"{clean_title}_raw.mp4")
    if not os.path.exists(expected_path):
        # Find the downloaded file
        for f in os.listdir(output_dir):
            if f.startswith(clean_title) and f.endswith(".mp4"):
                return os.path.join(output_dir, f), info["title"]
    return expected_path, info["title"]

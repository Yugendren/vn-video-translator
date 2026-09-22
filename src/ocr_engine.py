import os
import subprocess
import sys

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
SWIFT_SOURCE = os.path.join(SRC_DIR, "ocr.swift")
OCR_BIN = os.path.join(SRC_DIR, "ocr_bin")

def ensure_compiled():
    """Compiles ocr.swift into a native binary if not already present."""
    if os.path.exists(OCR_BIN) and os.path.getmtime(OCR_BIN) >= os.path.getmtime(SWIFT_SOURCE):
        return OCR_BIN
    
    print("[OCR] Compiling native Swift Vision OCR engine (Apple Neural Engine accelerated)...")
    cmd = ["swiftc", "-O", SWIFT_SOURCE, "-o", OCR_BIN]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[ERROR] Failed to compile ocr.swift:\n{res.stderr}")
        sys.exit(1)
    print("[OCR] Compiled OCR engine successfully.")
    return OCR_BIN

def run_ocr(video_path, output_json, interval=1.0, crop_y=0.72, crop_h=0.28, langs="zh-Hans,en-US"):
    """Runs the native OCR engine on the given video."""
    binary = ensure_compiled()
    cmd = [
        binary,
        video_path,
        output_json,
        str(interval),
        str(crop_y),
        str(crop_h),
        langs
    ]
    
    print(f"[OCR] Scanning dialogue across video frames ({interval}s interval)...")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout:
        print("  " + line.strip())
    proc.wait()
    
    if proc.returncode != 0:
        raise RuntimeError(f"OCR process exited with code {proc.returncode}")
    return output_json

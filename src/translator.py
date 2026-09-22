import os
import sys
import json
import time
import shutil
import subprocess
import urllib.request
import urllib.parse
import re
from .glossary import resolve_speaker

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(ROOT_DIR, ".env")
DEFAULT_MODEL_URL = "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"
DEFAULT_MODEL_NAME = "qwen2.5-3b-instruct-q4_k_m.gguf"

def load_env_file():
    """Reads .env file if present."""
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip("'\"")

def save_api_key_to_env(key):
    """Saves GEMINI_API_KEY to .env."""
    try:
        lines = []
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                lines = [l for l in f if not l.startswith("GEMINI_API_KEY=")]
        lines.append(f"GEMINI_API_KEY={key}\n")
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"💾 Saved GEMINI_API_KEY to {ENV_FILE}")
    except Exception as e:
        print(f"⚠️ Could not save to .env: {e}")

def resolve_api_key(provided_key=None, allow_prompt=True):
    """
    Retrieves the Gemini API key from arguments, environment, or .env.
    If not found, displays a guided prompt with the official Google AI Studio link.
    """
    load_env_file()
    if provided_key:
        return provided_key.strip()
    key = os.environ.get("GEMINI_API_KEY")
    if key and key.strip():
        return key.strip()
        
    if allow_prompt and sys.stdin.isatty():
        print("\n" + "╔" + "═" * 72 + "╗")
        print("║  🔑 Gemini API Key Required (Option 1)                                 ║")
        print("╠" + "═" * 72 + "╣")
        print("║  Option 1 uses Gemini 2.5 Flash for studio-quality localization.       ║")
        print("║  Get your free API key in 30 seconds from Google AI Studio:            ║")
        print("║                                                                        ║")
        print("║  👉 https://aistudio.google.com/app/apikey                             ║")
        print("║                                                                        ║")
        print("║  Quick Steps:                                                          ║")
        print("║  1. Open the URL above in your browser (log in with any Google account)║")
        print("║  2. Click '+ Create API key' (100% free)                               ║")
        print("║  3. Copy your key and paste it below                                   ║")
        print("╚" + "═" * 72 + "╝")
        
        entered = input("\nEnter your Gemini API Key (or press Enter to switch to Local Model): ").strip()
        if entered:
            save_choice = input("💾 Save key to .env so you don't have to enter it again? [Y/n]: ").strip().lower()
            if save_choice in ("", "y", "yes"):
                save_api_key_to_env(entered)
            os.environ["GEMINI_API_KEY"] = entered
            return entered
    return None

def check_llama_cpp_installed():
    """Returns the path to llama-server or llama-cli if installed, else None."""
    for bin_name in ["llama-server", "llama-cli"]:
        path = shutil.which(bin_name)
        if path:
            return path
    for std_path in ["/opt/homebrew/bin/llama-server", "/usr/local/bin/llama-server",
                     "/opt/homebrew/bin/llama-cli", "/usr/local/bin/llama-cli"]:
        if os.path.exists(std_path) and os.access(std_path, os.X_OK):
            return std_path
    return None

def ensure_llama_cpp_installed():
    """Verifies llama.cpp is installed; prompts to auto-install via brew on macOS if missing."""
    bin_path = check_llama_cpp_installed()
    if bin_path:
        return bin_path
        
    print("\n" + "╔" + "═" * 72 + "╗")
    print("║  ⚙️ llama.cpp is not installed                                         ║")
    print("╠" + "═" * 72 + "╣")
    print("║  Option 2 runs local models directly on your hardware (Metal GPU).     ║")
    print("║  It requires 'llama.cpp' (specifically llama-server or llama-cli).     ║")
    print("╚" + "═" * 72 + "╝")
    
    brew_bin = shutil.which("brew") or ("/opt/homebrew/bin/brew" if os.path.exists("/opt/homebrew/bin/brew") else None)
    
    if sys.platform == "darwin" and brew_bin and sys.stdin.isatty():
        ans = input("\nWould you like to install llama.cpp via Homebrew now? (brew install llama.cpp) [Y/n]: ").strip().lower()
        if ans in ("", "y", "yes"):
            print("\n📦 Running: brew install llama.cpp ... (this may take a couple minutes)")
            try:
                subprocess.run([brew_bin, "install", "llama.cpp"], check=True)
                bin_path = check_llama_cpp_installed()
                if bin_path:
                    print("✅ llama.cpp installed successfully!\n")
                    return bin_path
            except Exception as e:
                print(f"⚠️ Homebrew installation failed: {e}")
                
    print("\n💡 Please install llama.cpp manually:")
    print("   • macOS:   brew install llama.cpp")
    print("   • Ubuntu:  sudo apt install llama.cpp (or build from https://github.com/ggerganov/llama.cpp)")
    print("   • Windows: Download binaries from https://github.com/ggerganov/llama.cpp/releases")
    return None

def find_local_model():
    """Finds an existing GGUF model in ./models or HuggingFace cache."""
    # 1. Check ./models/ in the repo
    local_models = os.path.join(ROOT_DIR, "models")
    if os.path.exists(local_models):
        for f in os.listdir(local_models):
            if f.endswith(".gguf"):
                return os.path.join(local_models, f)
                
    # 2. Check HuggingFace hub cache
    hf_dir = os.path.expanduser("~/.cache/huggingface/hub")
    if os.path.exists(hf_dir):
        candidates = []
        for root, dirs, files in os.walk(hf_dir):
            for f in files:
                if f.endswith(".gguf"):
                    full_p = os.path.join(root, f)
                    if "qwen" in f.lower():
                        return full_p
                    candidates.append(full_p)
        if candidates:
            return candidates[0]
            
    return None

def download_file_with_progress(url, dest_path):
    """Downloads a file over HTTP with a real-time terminal progress bar."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    tmp_path = dest_path + ".tmp"
    filename = os.path.basename(dest_path)
    print(f"\n⬇️ Downloading {filename}...")
    print(f"   Source: {url}")
    
    req = urllib.request.Request(url, headers={"User-Agent": "VN-Video-Translator/1.0"})
    with urllib.request.urlopen(req) as resp:
        total_bytes = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 1024 * 1024  # 1MB
        start_time = time.time()
        last_update = start_time
        
        with open(tmp_path, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                
                now = time.time()
                if now - last_update >= 0.25 or downloaded == total_bytes:
                    elapsed = now - start_time
                    speed = downloaded / elapsed if elapsed > 0 else 0
                    speed_mb = speed / (1024 * 1024)
                    downloaded_mb = downloaded / (1024 * 1024)
                    total_mb = total_bytes / (1024 * 1024)
                    percent = (downloaded / total_bytes * 100) if total_bytes > 0 else 0
                    
                    eta_sec = int((total_bytes - downloaded) / speed) if speed > 0 and total_bytes > 0 else 0
                    eta_str = f"{eta_sec // 60}m {eta_sec % 60:02d}s" if eta_sec >= 60 else f"{eta_sec}s"
                    
                    bar_width = 25
                    filled = int(bar_width * percent / 100)
                    bar = "█" * filled + "░" * (bar_width - filled)
                    sys.stdout.write(f"\r  [{bar}] {percent:5.1f}% ({downloaded_mb:6.1f} / {total_mb:6.1f} MB) | {speed_mb:5.1f} MB/s | ETA: {eta_str:<6}")
                    sys.stdout.flush()
                    last_update = now
                    
    print("\n✅ Download complete!")
    if os.path.exists(dest_path):
        os.remove(dest_path)
    os.rename(tmp_path, dest_path)
    return dest_path

def ensure_local_model_exists(preferred_path=None):
    """Ensures a local GGUF model is available; prompts to download Qwen2.5-3B if missing."""
    if preferred_path and os.path.exists(preferred_path):
        return preferred_path
        
    found = find_local_model()
    if found:
        return found
        
    models_dir = os.path.join(ROOT_DIR, "models")
    target_path = os.path.join(models_dir, DEFAULT_MODEL_NAME)
    
    print("\n" + "╔" + "═" * 72 + "╗")
    print("║  🤖 No Local GGUF Model Found                                          ║")
    print("╠" + "═" * 72 + "╣")
    print("║  Option 2 requires a GGUF model for offline translation.               ║")
    print("║                                                                        ║")
    print("║  Recommended Model: Qwen 2.5 3B Instruct (Q4_K_M)                      ║")
    print("║  • Download size: ~2.0 GB (fits easily into 8GB+ RAM / Metal VRAM)     ║")
    print("║  • Quality: Top-tier Chinese & Japanese VN dialogue translation        ║")
    print("║  • Speed: ~35–50 tokens/sec on Apple Silicon Metal GPU                 ║")
    print("╚" + "═" * 72 + "╝")
    
    if sys.stdin.isatty():
        ans = input("\nWould you like to auto-download Qwen2.5-3B-Instruct now to ./models/? [Y/n]: ").strip().lower()
        if ans in ("", "y", "yes"):
            try:
                download_file_with_progress(DEFAULT_MODEL_URL, target_path)
                return target_path
            except KeyboardInterrupt:
                print("\n⚠️ Download cancelled by user.")
                if os.path.exists(target_path + ".tmp"):
                    os.remove(target_path + ".tmp")
                return None
            except Exception as e:
                print(f"\n⚠️ Download failed: {e}")
                if os.path.exists(target_path + ".tmp"):
                    os.remove(target_path + ".tmp")
                return None
                
    print("\n💡 You can manually download the model:")
    print(f"   curl -L -o models/{DEFAULT_MODEL_NAME} \"{DEFAULT_MODEL_URL}\"")
    print("   Or place any .gguf model into the models/ folder.")
    return None

class GeminiTranslator:
    def __init__(self, api_key, lore_manager, model="gemini-2.5-flash"):
        self.api_key = api_key
        self.lore_manager = lore_manager
        self.model = model

    def translate_batch(self, lines_batch, target_lang="English"):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        template, lore_context = self.lore_manager.build_system_prompt(target_lang=target_lang)
        
        prompt = template.format(
            game_context=self.lore_manager.game_title,
            target_lang=target_lang,
            lore_context=lore_context,
            input_lines=json.dumps(lines_batch, ensure_ascii=False, indent=2)
        )
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2
            }
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                resp_body = json.loads(response.read().decode('utf-8'))
                text_resp = resp_body["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text_resp)
        except Exception as e:
            print(f"⚠️ Gemini batch error: {e}")
            return lines_batch

class LocalLlamaTranslator:
    def __init__(self, lore_manager, model_path=None, port=8080):
        self.lore_manager = lore_manager
        self.port = port
        self.server_proc = None
        
        # Check llama.cpp installation
        self.server_bin = ensure_llama_cpp_installed()
        if not self.server_bin:
            raise RuntimeError("llama.cpp is required for Option 2. Please install with: brew install llama.cpp")
            
        # Check model file
        self.model_path = ensure_local_model_exists(model_path)
        if not self.model_path or not os.path.exists(self.model_path):
            raise FileNotFoundError("Local GGUF model not found. Please download Qwen2.5-3B or place a .gguf in models/")
        
    def ensure_server_running(self):
        # Check if already running on port
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{self.port}/health")
            with urllib.request.urlopen(req, timeout=1) as resp:
                if resp.status == 200:
                    return
        except Exception:
            pass
            
        print(f"⚡ Launching local llama-server with {os.path.basename(self.model_path)} on port {self.port}...")
        cmd = [
            self.server_bin,
            "-m", self.model_path,
            "--port", str(self.port),
            "-ngl", "99",
            "-c", "4096",
            "--log-disable"
        ]
        self.server_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Wait for server ready
        for _ in range(30):
            time.sleep(0.5)
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{self.port}/health")
                with urllib.request.urlopen(req, timeout=1) as resp:
                    if resp.status == 200:
                        print("✅ Local llama-server is ready!")
                        return
            except Exception:
                pass
        raise RuntimeError("Timed out waiting for llama-server to start.")

    def translate_batch(self, lines_batch, target_lang="English"):
        self.ensure_server_running()
        template, lore_context = self.lore_manager.build_system_prompt(target_lang=target_lang)
        prompt = template.format(
            game_context=self.lore_manager.game_title,
            target_lang=target_lang,
            lore_context=lore_context,
            input_lines=json.dumps(lines_batch, ensure_ascii=False, indent=2)
        )
        
        url = f"http://127.0.0.1:{self.port}/v1/chat/completions"
        payload = {
            "messages": [
                {"role": "system", "content": "You are a professional video game localization translator. Return valid JSON array."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                body = json.loads(response.read().decode('utf-8'))
                content = body["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    return parsed
                elif isinstance(parsed, dict):
                    for v in parsed.values():
                        if isinstance(v, list):
                            return v
                return lines_batch
        except Exception as e:
            print(f"⚠️ Local model translation error: {e}")
            return lines_batch

def select_engine(choice=None):
    """Interactively prompt user to choose Option 1 or Option 2 if not provided."""
    load_env_file()
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))
    
    if choice in ("1", "gemini"):
        return "gemini"
    if choice in ("2", "local"):
        return "local"
        
    # If key already configured and choice is auto, default to gemini
    if has_gemini:
        return "gemini"
        
    if not sys.stdin.isatty():
        return "gemini" if has_gemini else "local"
        
    print("\n" + "╔" + "═" * 72 + "╗")
    print("║        🤖 Choose Translation Engine                                    ║")
    print("╠" + "═" * 72 + "╣")
    print("║  [1] Option 1: Gemini Flash (Cloud, studio-quality, ~$0.001/video)     ║")
    print("║      • Nuanced personalities, lore fidelity, 3s translation speed     ║")
    print("║      • Requires free API key (https://aistudio.google.com/app/apikey)  ║")
    print("║                                                                        ║")
    print("║  [2] Option 2: Local Model  (Qwen 2.5 / llama.cpp, 100% offline)      ║")
    print("║      • Free, private, no API keys, runs on Apple Silicon Metal GPU    ║")
    print("╚" + "═" * 72 + "╝")
    
    user_choice = input("\nSelect option [1/2] (default: 1): ").strip()
    return "local" if user_choice == "2" else "gemini"

def translate_segments(segments, engine="auto", api_key=None, lore_manager=None, model_path=None, target_lang="English", batch_size=35):
    engine_selected = select_engine(engine)
    
    translator = None
    if engine_selected == "gemini":
        key = resolve_api_key(api_key)
        if not key:
            print("⚠️ Switching to Option 2 (Local Model) since no Gemini API key was provided.\n")
            try:
                translator = LocalLlamaTranslator(lore_manager=lore_manager, model_path=model_path)
            except Exception as e:
                print(f"❌ Failed to initialize Local Model: {e}")
                raise
        else:
            translator = GeminiTranslator(api_key=key, lore_manager=lore_manager)
    else:
        try:
            translator = LocalLlamaTranslator(lore_manager=lore_manager, model_path=model_path)
        except Exception as e:
            print(f"\n⚠️ Local Model setup could not be completed: {e}")
            if sys.stdin.isatty():
                retry = input("Would you like to switch to Option 1 (Gemini Flash Cloud) instead? [Y/n]: ").strip().lower()
                if retry in ("", "y", "yes"):
                    key = resolve_api_key(api_key)
                    if key:
                        translator = GeminiTranslator(api_key=key, lore_manager=lore_manager)
            if not translator:
                raise
        
    print(f"🌐 Translating {len(segments)} dialogue segments via {type(translator).__name__}...")
    
    # Format input lines with speaker context
    char_map = lore_manager.get_character_map() if lore_manager else {}
    input_items = []
    for s in segments:
        spk = resolve_speaker(s.get("speaker"), custom_map=char_map)
        txt = s.get("text", "")
        input_items.append(f"[{spk}] {txt}" if spk else txt)
        
    translated_results = []
    total = len(input_items)
    
    for i in range(0, total, batch_size):
        batch = input_items[i:i + batch_size]
        print(f"  Translating items {i + 1} to {min(i + batch_size, total)} of {total}...")
        batch_trans = translator.translate_batch(batch, target_lang=target_lang)
        
        for item in batch_trans:
            cleaned = re.sub(r'^\[[^\]]+\]\s*', '', str(item))
            translated_results.append(cleaned)
            
    # Pair translations back to segments
    translated_segments = []
    for idx, s in enumerate(segments):
        seg_copy = dict(s)
        seg_copy["en_text"] = translated_results[idx] if idx < len(translated_results) else s.get("text", "")
        translated_segments.append(seg_copy)
        
    # Stop local server if we started it
    if hasattr(translator, "server_proc") and translator.server_proc:
        translator.server_proc.terminate()
        
    print(f"✅ Finished translating {len(translated_segments)} segments.")
    return translated_segments

import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.parse
from .glossary import resolve_speaker

ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")

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
    load_env_file()
    if provided_key:
        return provided_key
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
        
    if allow_prompt and sys.stdin.isatty():
        print("\n🔑 No GEMINI_API_KEY found.")
        entered = input("Enter your Gemini API Key (or press Enter to cancel): ").strip()
        if entered:
            save_choice = input("Save this key to .env for future runs? [Y/n]: ").strip().lower()
            if save_choice in ("", "y", "yes"):
                save_api_key_to_env(entered)
            os.environ["GEMINI_API_KEY"] = entered
            return entered
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
        self.model_path = model_path or self.find_local_model()
        
    def find_local_model(self):
        # 1. Check HuggingFace cache
        hf_dir = os.path.expanduser("~/.cache/huggingface/hub")
        if os.path.exists(hf_dir):
            for root, dirs, files in os.walk(hf_dir):
                for f in files:
                    if f.endswith(".gguf") and ("qwen" in f.lower() or "llama" in f.lower()):
                        return os.path.join(root, f)
        # 2. Check ./models/
        local_models = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
        if os.path.exists(local_models):
            for f in os.listdir(local_models):
                if f.endswith(".gguf"):
                    return os.path.join(local_models, f)
        return None

    def ensure_server_running(self):
        if not self.model_path or not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Local GGUF model not found. Please place a .gguf model in models/ or specify --model-path")
            
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
            "llama-server",
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
                # Parse array or JSON object
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
        
    # If key exists and no choice specified, default to gemini
    if has_gemini:
        return "gemini"
        
    print("\n" + "=" * 58)
    print("        🤖 Choose Translation Engine")
    print("=" * 58)
    print("  [1] Option 1: Gemini Flash (Cloud, studio-quality, ~$0.001/video)")
    print("  [2] Option 2: Local Model  (Qwen / llama.cpp, 100% offline & free)")
    print("=" * 58)
    
    user_choice = input("Select option [1/2] (default: 2): ").strip()
    return "gemini" if user_choice == "1" else "local"

def translate_segments(segments, engine="auto", api_key=None, lore_manager=None, model_path=None, target_lang="English", batch_size=35):
    engine_selected = select_engine(engine)
    
    if engine_selected == "gemini":
        key = resolve_api_key(api_key)
        if not key:
            print("⚠️ Switching to Local Model since no Gemini API key was provided.")
            translator = LocalLlamaTranslator(lore_manager=lore_manager, model_path=model_path)
        else:
            translator = GeminiTranslator(api_key=key, lore_manager=lore_manager)
    else:
        translator = LocalLlamaTranslator(lore_manager=lore_manager, model_path=model_path)
        
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
            import re
            cleaned = re.sub(r'^\[[^\]]+\]\s*', '', item)
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

import os
import json
import urllib.request
import urllib.parse
from .glossary import resolve_speaker

def translate_batch_gemini(lines_batch, api_key, game_context="Visual Novel / Anime Game Story", target_lang="English", model="gemini-2.5-flash"):
    """
    Translates a batch of dialogue items using the Gemini Flash REST API.
    Zero external SDK required.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    prompt = f"""You are a professional video game localization translator.
Translate the following dialogue lines from a {game_context} into natural, immersive, and lore-accurate {target_lang}.

Output a JSON array of strings corresponding 1:1 with the input items in the exact same order.
Maintain all narrative tone, distinct character personality, and dialogue immersion.

Input lines to translate:
{json.dumps(lines_batch, ensure_ascii=False, indent=2)}

Return ONLY valid JSON matching:
[
  "translated line 1",
  "translated line 2",
  ...
]
"""
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2
        }
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            resp_body = json.loads(response.read().decode('utf-8'))
            text_resp = resp_body["candidates"][0]["content"]["parts"][0]["text"]
            translations = json.loads(text_resp)
            return translations
    except Exception as e:
        print(f"⚠️ Gemini API batch error: {e}")
        # Fallback to returning original lines if API fails
        return lines_batch

def translate_segments(segments, api_key=None, game_context="Visual Novel", target_lang="English", batch_size=40):
    """
    Translates all segments, injecting resolved speakers and grouping into batches.
    """
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")
        
    if not api_key:
        print("⚠️ No GEMINI_API_KEY provided. Please set GEMINI_API_KEY or enter it.")
        api_key = input("Enter your Gemini API Key: ").strip()
        
    print(f"🌐 Translating {len(segments)} dialogue segments via Gemini Flash...")
    
    # Prepare lines with speaker context for better translation accuracy
    input_items = []
    for s in segments:
        spk = resolve_speaker(s.get("speaker"))
        txt = s.get("text", "")
        if spk:
            input_items.append(f"[{spk}] {txt}")
        else:
            input_items.append(txt)
            
    translated_results = []
    total = len(input_items)
    
    for i in range(0, total, batch_size):
        batch = input_items[i:i + batch_size]
        print(f"  Translating items {i + 1} to {min(i + batch_size, total)} of {total}...")
        batch_trans = translate_batch_gemini(batch, api_key, game_context, target_lang)
        
        # Clean speaker prefix from translation if returned
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
        
    print(f"✅ Finished translating {len(translated_segments)} segments.")
    return translated_segments

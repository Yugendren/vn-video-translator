import re
import json

UI_PATTERNS = [
    r'^\d+/\d+',
    r'再收集\d+可领取',
    r'英雄难',
    r'普通难',
    r'剧情',
    r'物资',
    r'观看',
    r'自动',
    r'跳过',
    r'全部跳过',
    r'^ANG[I\+]?',
    r'^ANE',
    r'点击空白处关闭',
    r'Log',
    r'Auto',
    r'Skip',
]

def clean_lines(lines):
    filtered = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        is_ui = any(re.search(pat, line, re.IGNORECASE) for pat in UI_PATTERNS)
        if not is_ui:
            filtered.append(line)
    return filtered

def parse_speaker_and_text(filtered_lines):
    if not filtered_lines:
        return None, ""
    
    first = filtered_lines[0].strip()
    first_cleaned = re.sub(r'^[|Iim灬\s\u2022•\.\-]+', '', first)
    
    speaker = None
    text_lines = []
    
    # Speaker followed by colon: "Name: Text"
    m = re.match(r'^([^：:]{1,8})[：:](.*)$', first_cleaned)
    if m:
        speaker = m.group(1).strip()
        rem = m.group(2).strip()
        if rem:
            text_lines.append(rem)
        text_lines.extend(filtered_lines[1:])
    # First line is standalone speaker name
    elif len(first_cleaned) <= 6 and not any(p in first_cleaned for p in '，。？！、（）…') and len(filtered_lines) > 1:
        speaker = first_cleaned
        text_lines.extend(filtered_lines[1:])
    else:
        text_lines.extend(filtered_lines)
    
    text = " ".join(text_lines).strip()
    text = re.sub(r'^[|Iim灬\s\u2022•\.\-]+', '', text)
    text = re.sub(r'\s+', ' ', text)
    return speaker, text

def is_similar(t1, t2):
    if not t1 or not t2:
        return False
    if t1 in t2 or t2 in t1:
        return True
    s1, s2 = set(t1), set(t2)
    overlap = len(s1 & s2)
    return overlap / min(len(s1), len(s2)) >= 0.50

def segment_raw_frames(raw_frames_path, output_segments_path=None):
    with open(raw_frames_path, 'r', encoding='utf-8') as f:
        frames = json.load(f)
    
    parsed_frames = []
    for f in frames:
        lines = clean_lines(f.get("lines", []))
        spk, txt = parse_speaker_and_text(lines)
        if len(txt) >= 2 or spk:
            parsed_frames.append({
                "time": f["time"],
                "speaker": spk,
                "text": txt
            })
    
    segments = []
    current = None
    
    for pf in parsed_frames:
        t = pf["time"]
        spk = pf["speaker"]
        txt = pf["text"]
        
        if not current:
            current = {"start": t, "end": t + 1.2, "speaker": spk, "text": txt}
            continue
        
        time_gap = t - current["end"]
        same_speaker = (current["speaker"] == spk) or (not current["speaker"] and not spk) or (spk and not current["speaker"])
        similar_text = is_similar(current["text"], txt)
        
        if time_gap <= 3.0 and (same_speaker and similar_text):
            current["end"] = t + 1.2
            if spk and not current["speaker"]:
                current["speaker"] = spk
            if len(txt) > len(current["text"]):
                current["text"] = txt
        else:
            if len(current["text"]) >= 2:
                segments.append(current)
            current = {"start": t, "end": t + 1.2, "speaker": spk, "text": txt}
            
    if current and len(current["text"]) >= 2:
        segments.append(current)
        
    # Pass 2: Merge typewriter prefixes and fragments
    merged = []
    i = 0
    while i < len(segments):
        curr = dict(segments[i])
        while i + 1 < len(segments):
            nxt = segments[i + 1]
            if nxt["start"] - curr["end"] <= 2.0:
                c_txt = curr["text"]
                n_txt = nxt["text"]
                is_prefix = (c_txt in n_txt) or (n_txt in c_txt)
                s_c, s_n = set(c_txt), set(n_txt)
                overlap = len(s_c & s_n) / min(len(s_c), len(s_n)) if min(len(s_c), len(s_n)) > 0 else 0
                is_short = len(c_txt) <= 4 and (curr["speaker"] == nxt["speaker"] or not curr["speaker"])
                
                if is_prefix or overlap >= 0.5 or is_short:
                    curr["end"] = max(curr["end"], nxt["end"])
                    if len(n_txt) >= len(c_txt):
                        curr["text"] = n_txt
                    if not curr["speaker"] and nxt["speaker"]:
                        curr["speaker"] = nxt["speaker"]
                    i += 1
                    continue
            break
        merged.append(curr)
        i += 1
        
    cleaned = [m for m in merged if len(m["text"].strip()) >= 3 or (len(m["text"].strip()) >= 2 and m["speaker"])]
    
    if output_segments_path:
        with open(output_segments_path, 'w', encoding='utf-8') as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)
            
    print(f"[SEGMENTER] Aggregated {len(frames)} raw frames into {len(cleaned)} stabilized dialogue lines.")
    return cleaned

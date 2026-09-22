# Known canonical names and terms for VN / Anime games

GFL_SPEAKER_MAP = {
    "格琳娜": "Kalina",
    "闪电": "Groza",
    "乌尔丽德": "Ulrid",
    "莱娅": "Leya",
    "罗贝蒂": "Roberti",
    "纳美西丝": "Nemesis",
    "莱娜": "Lena",
    "莉塔拉": "Littara",
    "美玲": "Meiling",
    "佩里缇亚": "Peritya",
    "梦想家": "Dreamer",
    "兰汀": "Lanting",
    "兰订": "Lanting",
    "建筑师": "Architect",
    "代理人": "Agent",
    "计量官": "Gager",
    "破坏者": "Destroyer",
    "法官": "Judge",
    "干扰者": "Intruder",
    "炼金术士": "Alchemist",
    "克罗丽科": "Krolik",
    "寇尔芙": "Colphne",
    "维普蕾": "Vepley",
    "春田": "Springfield",
    "莫辛纳甘": "Mosin-Nagant",
    "琼玖": "Qionjiu",
    "托洛洛": "Tololo",
    "奇塔": "Cheeta",
    "琳德": "Lind",
    "可露凯": "Klukai",
    "索普": "Sopmod",
    "米蒂尔": "Mithil",
    "卡萝": "Caro",
}

def resolve_speaker(raw, custom_map=None):
    if not raw:
        return None
    mapping = {**GFL_SPEAKER_MAP, **(custom_map or {})}
    for k, v in mapping.items():
        if k in raw:
            return v
    # If no mapping, clean up OCR marks and return cleaned name
    import re
    cleaned = re.sub(r'^[|Iim灬\s\u2022•\.\-]+', '', raw).strip()
    return cleaned if len(cleaned) <= 12 else None

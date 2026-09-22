import os
import textwrap
from PIL import ImageFont

FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")

FONT_PRESETS = {
    "latex": os.path.join(FONTS_DIR, "STIXTwoText.ttf"),
    "tex": os.path.join(FONTS_DIR, "STIXTwoText.ttf"),
    "stix": os.path.join(FONTS_DIR, "STIXTwoText.ttf"),
    "arial": os.path.join(FONTS_DIR, "Arial.ttf"),
    "sans": os.path.join(FONTS_DIR, "Arial.ttf"),
    "times": os.path.join(FONTS_DIR, "TimesNewRoman.ttf"),
    "serif": os.path.join(FONTS_DIR, "TimesNewRoman.ttf"),
}

def resolve_font_path(font_name_or_path):
    """Resolves font name/preset or absolute path."""
    if not font_name_or_path:
        return FONT_PRESETS["latex"]
    
    lower = font_name_or_path.lower().strip()
    if lower in FONT_PRESETS:
        return FONT_PRESETS[lower]
        
    if os.path.exists(font_name_or_path):
        return font_name_or_path
        
    # Check assets/fonts
    in_assets = os.path.join(FONTS_DIR, font_name_or_path)
    if os.path.exists(in_assets):
        return in_assets
        
    # Fallback to LaTeX font
    return FONT_PRESETS["latex"]

def resolve_speaker_font(font_path):
    """Returns matching bold font for speaker if available."""
    if "Arial" in font_path:
        bold_path = os.path.join(FONTS_DIR, "ArialBold.ttf")
        if os.path.exists(bold_path):
            return bold_path
    return font_path

def fit_dialogue_text(
    draw,
    text,
    max_w,
    max_h,
    font_path,
    base_size=28,
    min_size=16,
    line_spacing=7
):
    """
    Dynamically fits text into available width and height:
    - If it fits at base_size, keeps base_size fixed for visual consistency.
    - If it exceeds boundaries, iteratively decrements font size until it fits cleanly.
    - Prevents word collision and out-of-bounds overflow.
    """
    current_size = base_size
    
    while current_size >= min_size:
        font = ImageFont.truetype(font_path, current_size)
        
        # Estimate character width
        sample_bbox = font.getbbox("M")
        char_w = max(sample_bbox[2] - sample_bbox[0], 1)
        # Average character width is roughly 0.65 * char_w
        wrap_width = max(int(max_w / (char_w * 0.72)), 25)
        
        wrapped_lines = textwrap.wrap(text, width=wrap_width)
        wrapped_text = "\n".join(wrapped_lines)
        
        bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font, spacing=line_spacing)
        rendered_w = bbox[2] - bbox[0]
        rendered_h = bbox[3] - bbox[1]
        
        if rendered_w <= max_w and rendered_h <= max_h:
            return font, wrapped_text, current_size
            
        current_size -= 1
        
    # Fallback at min_size
    font = ImageFont.truetype(font_path, min_size)
    sample_bbox = font.getbbox("M")
    char_w = max(sample_bbox[2] - sample_bbox[0], 1)
    wrap_width = max(int(max_w / (char_w * 0.72)), 25)
    wrapped_lines = textwrap.wrap(text, width=wrap_width)
    return font, "\n".join(wrapped_lines), min_size

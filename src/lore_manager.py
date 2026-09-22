import os
import json

LORE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lore")
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")

class LoreManager:
    def __init__(self, lore_path=None, scene_context=None, game_title=None):
        self.lore_data = {}
        self.scene_context = scene_context or ""
        self.game_title = game_title or "Visual Novel / Anime Game"
        
        # Load preset if file exists or name matches
        if lore_path:
            self.load_lore(lore_path)
            
    def load_lore(self, path):
        # Check direct path
        target = path
        if not os.path.exists(target):
            # Check inside lore/
            in_lore = os.path.join(LORE_DIR, path if path.endswith('.json') else f"{path}.json")
            if os.path.exists(in_lore):
                target = in_lore
                
        if os.path.exists(target):
            try:
                with open(target, 'r', encoding='utf-8') as f:
                    self.lore_data = json.load(f)
                self.game_title = self.lore_data.get("game_title", self.game_title)
                print(f"[LORE] Loaded preset: {self.game_title} ({os.path.basename(target)})")
            except Exception as e:
                print(f"[WARN] Failed to load lore file {target}: {e}")

    def get_character_map(self):
        """Returns dict of {OriginalName: EnglishName}."""
        mapping = {}
        for orig, info in self.lore_data.get("characters", {}).items():
            if isinstance(info, dict):
                mapping[orig] = info.get("en_name", orig)
            elif isinstance(info, str):
                mapping[orig] = info
        return mapping

    def format_lore_context(self):
        """Builds structured lore prompt section."""
        sections = []
        
        synopsis = self.lore_data.get("synopsis", "")
        if synopsis:
            sections.append(f"### Story Background & Setting:\n{synopsis}")
            
        if self.scene_context:
            sections.append(f"### Current Scene Context:\n{self.scene_context}")
            
        chars = self.lore_data.get("characters", {})
        if chars:
            char_lines = []
            for orig, info in chars.items():
                if isinstance(info, dict):
                    en = info.get("en_name", orig)
                    voice = info.get("voice", "")
                    char_lines.append(f"- {orig} -> {en} (Tone: {voice})")
                else:
                    char_lines.append(f"- {orig} -> {info}")
            sections.append("### Character Roster & Speech Styles:\n" + "\n".join(char_lines))
            
        glossary = self.lore_data.get("glossary", {})
        if glossary:
            terms = [f"- {zh} = {en}" for zh, en in glossary.items()]
            sections.append("### Terminology & Faction Glossary:\n" + "\n".join(terms))
            
        return "\n\n".join(sections)

    def build_system_prompt(self, target_lang="English"):
        template_path = os.path.join(CONFIG_DIR, "prompt_template.txt")
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
        else:
            template = "You are an expert translator. Translate from {game_context} to {target_lang}.\n\n{lore_context}\n\n{input_lines}"
            
        lore_context = self.format_lore_context()
        return template, lore_context

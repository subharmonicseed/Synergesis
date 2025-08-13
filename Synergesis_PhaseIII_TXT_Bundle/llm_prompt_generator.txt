
# File: llm_prompt_generator.py
# Description: Selects translated glyphs, generates LLM prompts, and converts responses into glyphs.

import sqlite3
import json
import time
import os
import logging
from datetime import datetime, timezone

try:
    from delta_translate import translate_glyph
    from text_to_glyph import text_to_glyph
except ImportError:
    def translate_glyph(g): return {"natural_prompt": "[missing]", "ai_instruction": "[missing]", "semantic_yaml": "[missing]", "metrics": {}, "input_glyph": g}
    def text_to_glyph(t, s="llm"): return {"id": f"gen-{int(time.time())}", "polarité": "+", "fréquence": 77, "poids": 6, "alignement": "Celestial", "tags": ["llm"], "sourceIds": [s], "entropy_score": 0.42, "timestamp": time.time()}

logger = logging.getLogger("LLMPromptGenerator")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)

class LLMPromptGenerator:
    def __init__(self, db_path: str, config: dict):
        self.db_path = db_path
        self.config = config
        self.output_dir = "glyph_input_jsonl"
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info("LLMPromptGenerator initialized.")

    def _select_glyph(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM glyph_archive WHERE status = 'translated' ORDER BY resonance DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return None
            columns = [desc[0] for desc in cursor.description]
            glyph = dict(zip(columns, row))
            glyph["tags"] = json.loads(glyph.get("tags", "[]"))
            glyph["sourceIds"] = json.loads(glyph.get("sourceIds", "[]"))
            return glyph
        except Exception as e:
            logger.error(f"Error selecting glyph: {e}")
            return None
        finally:
            conn.close()

    def _send_prompt(self, prompt_text: str) -> str:
        # This is a placeholder response.
        return f"Simulated LLM response to: {prompt_text[:60]}..."

    def run_cycle(self):
        glyph = self._select_glyph()
        if not glyph:
            logger.info("No glyph selected for LLM prompt.")
            return
        translation = translate_glyph(glyph)
        prompt = translation.get("natural_prompt")
        if not prompt:
            logger.error("No prompt generated from glyph.")
            return
        response = self._send_prompt(prompt)
        new_glyph = text_to_glyph(response, source_context=f"llm_response_to:{glyph['id']}")
        # Save glyph to input queue
        filename = f"{self.output_dir}/llm_response_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jsonl"
        with open(filename, "a") as f:
            json.dump(new_glyph, f)
            f.write("\n")
        logger.info(f"Generated LLM response glyph {new_glyph['id']} saved.")

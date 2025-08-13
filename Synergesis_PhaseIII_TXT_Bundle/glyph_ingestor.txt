
# File: glyph_ingestor.py
# Description: Fetches external text data and converts it to glyphs for Synergesis.

import time
import json
import os
import logging
from datetime import datetime, timezone

try:
    from text_to_glyph import text_to_glyph
except ImportError:
    def text_to_glyph(text, source_context="ingestor"):
        return {
            'id': f"glyph-{int(time.time())}",
            'polarité': '+',
            'fréquence': 88,
            'poids': 7,
            'alignement': 'Celestial',
            'tags': ['mock'],
            'sourceIds': [source_context],
            'entropy_score': 0.55,
            'timestamp': time.time()
        }

logger = logging.getLogger("GlyphIngestor")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)

RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://feeds.reuters.com/reuters/topNews"
]
OUTPUT_DIR = 'glyph_input_jsonl'
PROCESSED_IDS_FILE = 'processed_feed_ids.txt'

def load_processed_ids():
    if os.path.exists(PROCESSED_IDS_FILE):
        with open(PROCESSED_IDS_FILE, 'r') as f:
            return set(line.strip() for line in f)
    return set()

def save_processed_id(item_id: str):
    with open(PROCESSED_IDS_FILE, 'a') as f:
        f.write(item_id + '\n')

def ingest_rss_item(title: str, link: str, item_id: str):
    glyph = text_to_glyph(title, source_context="rss")
    glyph['tags'].append("rss")
    filename = f"{OUTPUT_DIR}/glyphs_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
    with open(filename, 'a') as f:
        json.dump(glyph, f)
        f.write('\n')
    save_processed_id(item_id)
    logger.info(f"Ingested: {title}")

def run_ingestor():
    logger.info("Running simple glyph ingestor loop...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    processed_ids = load_processed_ids()

    try:
        import feedparser
        for feed in RSS_FEEDS:
            parsed = feedparser.parse(feed)
            for entry in parsed.entries[:5]:
                item_id = entry.get('id') or entry.get('link')
                if item_id and item_id not in processed_ids:
                    title = entry.get('title', 'No Title')
                    ingest_rss_item(title, entry.get('link'), item_id)
    except Exception as e:
        logger.error(f"RSS ingestion failed: {e}")

if __name__ == "__main__":
    run_ingestor()

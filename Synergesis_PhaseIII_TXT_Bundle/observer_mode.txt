
# File: observer_mode.py
# Description: Periodically observes the Glyph Archive state and generates summary glyphs.

import sqlite3
import pandas as pd
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

try:
    from text_to_glyph import text_to_glyph
except ImportError:
    def text_to_glyph(text, source_context="observer"):
        return {
            'id': f"observer-glyph-{int(time.time())}",
            'polarité': '0',
            'fréquence': 55,
            'poids': 4,
            'alignement': 'Void',
            'tags': ['observer'],
            'sourceIds': [source_context],
            'entropy_score': 0.66,
            'timestamp': time.time()
        }

logger = logging.getLogger("ObserverMode")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)

class Observer:
    def __init__(self, db_path: str, config: Dict):
        self.db_path = db_path
        self.config = config
        logger.info("Observer initialized.")

    def _get_recent_data(self, hours: int = 6) -> pd.DataFrame:
        conn = sqlite3.connect(self.db_path)
        try:
            threshold = (datetime.utcnow() - timedelta(hours=hours)).timestamp()
            query = "SELECT * FROM glyph_archive WHERE timestamp >= ?"
            df = pd.read_sql_query(query, conn, params=(threshold,))
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
            return df
        except Exception as e:
            logger.error(f"Error reading DB: {e}")
            return pd.DataFrame()
        finally:
            conn.close()

    def summarize_state(self, df: pd.DataFrame) -> Optional[Dict]:
        if df.empty or len(df) < 10:
            logger.info("Not enough glyphs to observe.")
            return None

        summary = {
            'count': len(df),
            'polarité_dist': df['polarité'].value_counts().to_dict(),
            'alignement_dist': df['alignement'].value_counts().to_dict(),
            'avg_resonance': df['resonance'].mean() if 'resonance' in df.columns else None,
            'avg_emergence': df['emergence'].mean() if 'emergence' in df.columns else None,
            'avg_entropy': df['entropy_score'].mean() if 'entropy_score' in df.columns else None
        }
        return summary

    def generate_observation_glyph(self, summary: Dict) -> Optional[Dict]:
        if not summary:
            return None
        text = (
            f"System observation. {summary['count']} glyphs. "
            f"Avg resonance: {summary.get('avg_resonance', '?'):.2f}. "
            f"Polarity distribution: {summary['polarité_dist']}. "
            f"Alignment: {summary['alignement_dist']}."
        )
        return text_to_glyph(text, source_context="observer_summary")

    def run_observation(self) -> Optional[Dict]:
        df = self._get_recent_data()
        summary = self.summarize_state(df)
        return self.generate_observation_glyph(summary)

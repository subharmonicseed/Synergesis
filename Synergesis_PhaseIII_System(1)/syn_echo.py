
# File: syn_echo.py
# Description: Detects symbolic echoes and chains in the glyph archive.

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger("SynergesisEcho")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)

class EchoDetector:
    def __init__(self, db_path: str):
        self.db_path = db_path
        logger.info("EchoDetector initialized.")

    def _get_recent_glyphs(self, lookback_days: int = 7) -> pd.DataFrame:
        conn = sqlite3.connect(self.db_path)
        try:
            threshold = (datetime.utcnow() - timedelta(days=lookback_days)).timestamp()
            df = pd.read_sql_query(
                "SELECT id, timestamp, polarité, fréquence, poids, alignement, tags, resonance FROM glyph_archive WHERE timestamp >= ?",
                conn, params=(threshold,)
            )
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
                df['tags'] = df['tags'].apply(lambda x: json.loads(x) if isinstance(x, str) else [])
            return df
        finally:
            conn.close()

    def find_exact_repeats(self, df: pd.DataFrame, min_count: int = 3) -> dict:
        echoes = {}
        if df.empty:
            return echoes
        df['key'] = df.apply(lambda r: (r['polarité'], r['fréquence'], r['poids'], r['alignement']), axis=1)
        counts = df['key'].value_counts()
        repeated = counts[counts >= min_count]
        for key in repeated.index:
            matches = df[df['key'] == key][['id', 'timestamp']].to_dict('records')
            echoes[str(key)] = matches
        return echoes

    def find_resonant_chains(self, df: pd.DataFrame, threshold: float = 60.0, min_length: int = 3) -> list:
        chains = []
        current = []
        for _, row in df.sort_values("timestamp").iterrows():
            if row.get("resonance", 0) >= threshold:
                current.append(row.to_dict())
            else:
                if len(current) >= min_length:
                    chains.append(current)
                current = []
        if len(current) >= min_length:
            chains.append(current)
        return chains

    def detect_echoes(self) -> dict:
        df = self._get_recent_glyphs()
        exact = self.find_exact_repeats(df)
        chains = self.find_resonant_chains(df)
        logger.info(f"Echo detection found {len(exact)} repeat patterns and {len(chains)} chains.")
        return {
            "exact_repeats": exact,
            "resonant_chains": chains,
            "total_glyphs": len(df),
            "timestamp": datetime.utcnow().isoformat()
        }

if __name__ == "__main__":
    detector = EchoDetector("glyph_archive.db")
    report = detector.detect_echoes()
    print(json.dumps(report, indent=2))

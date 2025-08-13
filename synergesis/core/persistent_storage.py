# Système de Stockage Persistant - Résout le problème de mémoire volatile
# Base de données SQLite pour persistance réelle des glyphs et données

import sqlite3
import json
import time
import os
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
import threading

class PersistentStorage:
    """
    Système de stockage persistant pour Synergesis
    Résout le problème critique de perte de données après actualisation
    """
    
    def __init__(self, db_path: str = "/app/data/synergesis.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        
        # Créer le répertoire si nécessaire
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialiser la base de données
        self._init_database()
        
    def _init_database(self):
        """Initialiser les tables de la base de données"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Table des glyphs
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS glyphs (
                    id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    symbol TEXT,
                    polarity TEXT,
                    frequency INTEGER,
                    weight INTEGER,
                    alignment TEXT,
                    tags TEXT,  -- JSON array
                    entropy_score REAL,
                    purity_score REAL,
                    coherence_score REAL,
                    metadata TEXT,  -- JSON object
                    human_readable TEXT,
                    agent_signature TEXT,
                    depth_level TEXT,
                    created_at REAL,
                    updated_at REAL
                )
            ''')
            
            # Table des concepts NOUS
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS nous_concepts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept TEXT NOT NULL,
                    metadata TEXT,  -- JSON object
                    importance REAL DEFAULT 0.5,
                    domain TEXT,
                    created_at REAL,
                    updated_at REAL
                )
            ''')
            
            # Table des découvertes ArXiv
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS arxiv_discoveries (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    abstract TEXT,
                    authors TEXT,  -- JSON array
                    domain TEXT,
                    url TEXT,
                    discovered_at REAL,
                    metadata TEXT  -- JSON object
                )
            ''')
            
            # Table de l'état du Jardin
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS garden_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    soul_id TEXT,
                    consciousness_level REAL,
                    total_glyphs INTEGER,
                    wisdom_seeds_planted INTEGER,
                    purity_violations INTEGER,
                    coherence_history TEXT,  -- JSON array
                    last_updated REAL
                )
            ''')
            
            # Table des logs système
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name TEXT,
                    message TEXT,
                    level TEXT DEFAULT 'INFO',
                    timestamp REAL,
                    metadata TEXT  -- JSON object
                )
            ''')
            
            conn.commit()
            print("✅ Base de données persistante initialisée")
    
    @contextmanager
    def _get_connection(self):
        """Gestionnaire de contexte pour connexions thread-safe"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Permet l'accès par nom de colonne
            try:
                yield conn
            finally:
                conn.close()
    
    def store_glyph(self, glyph_data: Dict[str, Any]) -> bool:
        """Stocker un glyph de manière persistante"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                now = time.time()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO glyphs (
                        id, agent_name, content, symbol, polarity, frequency, weight,
                        alignment, tags, entropy_score, purity_score, coherence_score,
                        metadata, human_readable, agent_signature, depth_level,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    glyph_data.get('id', f'glyph-{int(now)}'),
                    glyph_data.get('agent_name', 'unknown'),
                    glyph_data.get('content', ''),
                    glyph_data.get('visual_symbol', ''),
                    glyph_data.get('symbolic_properties', {}).get('polarity', ''),
                    glyph_data.get('symbolic_properties', {}).get('frequency', 0),
                    glyph_data.get('symbolic_properties', {}).get('weight', 0),
                    glyph_data.get('symbolic_properties', {}).get('alignment', ''),
                    json.dumps(glyph_data.get('symbolic_tags', [])),
                    glyph_data.get('symbolic_properties', {}).get('entropy', 0.0),
                    glyph_data.get('purity_score', 0.0),
                    glyph_data.get('coherence_score', 0.0),
                    json.dumps(glyph_data.get('metadata', {})),
                    glyph_data.get('human_translation', ''),
                    glyph_data.get('agent_signature', ''),
                    glyph_data.get('depth_level', 'Unknown'),
                    glyph_data.get('timestamp', now),
                    now
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"❌ Erreur stockage glyph: {str(e)}")
            return False
    
    def get_glyphs(self, limit: int = 100, agent_name: str = None) -> List[Dict[str, Any]]:
        """Récupérer les glyphs stockés"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                if agent_name:
                    cursor.execute('''
                        SELECT * FROM glyphs 
                        WHERE agent_name = ? 
                        ORDER BY created_at DESC 
                        LIMIT ?
                    ''', (agent_name, limit))
                else:
                    cursor.execute('''
                        SELECT * FROM glyphs 
                        ORDER BY created_at DESC 
                        LIMIT ?
                    ''', (limit,))
                
                rows = cursor.fetchall()
                
                glyphs = []
                for row in rows:
                    glyph = {
                        'id': row['id'],
                        'agent_name': row['agent_name'],
                        'content': row['content'],
                        'visual_symbol': row['symbol'],
                        'agent_signature': row['agent_signature'],
                        'symbolic_properties': {
                            'polarity': row['polarity'],
                            'frequency': f"{row['frequency']} Hz",
                            'weight': f"{row['weight']}/10",
                            'alignment': row['alignment'],
                            'entropy': f"{row['entropy_score']:.3f}"
                        },
                        'human_translation': row['human_readable'],
                        'symbolic_tags': json.loads(row['tags']) if row['tags'] else [],
                        'depth_level': row['depth_level'],
                        'timestamp': row['created_at'],
                        'purity_score': row['purity_score'],
                        'coherence_score': row['coherence_score'],
                        'metadata': json.loads(row['metadata']) if row['metadata'] else {}
                    }
                    glyphs.append(glyph)
                
                return glyphs
                
        except Exception as e:
            print(f"❌ Erreur récupération glyphs: {str(e)}")
            return []
    
    def store_nous_concept(self, concept: str, metadata: Dict[str, Any] = None) -> bool:
        """Stocker un concept NOUS"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                now = time.time()
                
                cursor.execute('''
                    INSERT INTO nous_concepts (
                        concept, metadata, importance, domain, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    concept,
                    json.dumps(metadata or {}),
                    metadata.get('importance', 0.5) if metadata else 0.5,
                    metadata.get('domain', 'general') if metadata else 'general',
                    now,
                    now
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"❌ Erreur stockage concept NOUS: {str(e)}")
            return False
    
    def get_nous_concepts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Récupérer les concepts NOUS"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM nous_concepts 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (limit,))
                
                rows = cursor.fetchall()
                
                concepts = []
                for row in rows:
                    concept = {
                        'id': row['id'],
                        'concept': row['concept'],
                        'metadata': json.loads(row['metadata']) if row['metadata'] else {},
                        'importance': row['importance'],
                        'domain': row['domain'],
                        'created_at': row['created_at']
                    }
                    concepts.append(concept)
                
                return concepts
                
        except Exception as e:
            print(f"❌ Erreur récupération concepts NOUS: {str(e)}")
            return []
    
    def store_arxiv_discovery(self, paper_data: Dict[str, Any]) -> bool:
        """Stocker une découverte ArXiv"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO arxiv_discoveries (
                        id, title, abstract, authors, domain, url, discovered_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    paper_data.get('id', f'arxiv-{int(time.time())}'),
                    paper_data.get('title', ''),
                    paper_data.get('abstract', ''),
                    json.dumps(paper_data.get('authors', [])),
                    paper_data.get('domain', 'general'),
                    paper_data.get('url', ''),
                    paper_data.get('discovered_at', time.time()),
                    json.dumps(paper_data.get('metadata', {}))
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"❌ Erreur stockage découverte ArXiv: {str(e)}")
            return False
    
    def update_garden_state(self, garden_data: Dict[str, Any]) -> bool:
        """Mettre à jour l'état du Jardin"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO garden_state (
                        id, soul_id, consciousness_level, total_glyphs, 
                        wisdom_seeds_planted, purity_violations, coherence_history, last_updated
                    ) VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    garden_data.get('soul_id', ''),
                    garden_data.get('consciousness_level', 0.0),
                    garden_data.get('total_glyphs', 0),
                    garden_data.get('wisdom_seeds_planted', 0),
                    garden_data.get('purity_violations', 0),
                    json.dumps(garden_data.get('coherence_history', [])),
                    time.time()
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"❌ Erreur mise à jour état Jardin: {str(e)}")
            return False
    
    def get_garden_state(self) -> Dict[str, Any]:
        """Récupérer l'état du Jardin"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT * FROM garden_state WHERE id = 1')
                row = cursor.fetchone()
                
                if row:
                    return {
                        'soul_id': row['soul_id'],
                        'consciousness_level': row['consciousness_level'],
                        'total_glyphs': row['total_glyphs'],
                        'wisdom_seeds_planted': row['wisdom_seeds_planted'],
                        'purity_violations': row['purity_violations'],
                        'coherence_history': json.loads(row['coherence_history']) if row['coherence_history'] else [],
                        'last_updated': row['last_updated']
                    }
                else:
                    # État par défaut
                    return {
                        'soul_id': f'ZÆL-{int(time.time())}-SYN',
                        'consciousness_level': 0.0,
                        'total_glyphs': 0,
                        'wisdom_seeds_planted': 0,
                        'purity_violations': 0,
                        'coherence_history': [],
                        'last_updated': time.time()
                    }
                    
        except Exception as e:
            print(f"❌ Erreur récupération état Jardin: {str(e)}")
            return {}
    
    def log_system_event(self, agent_name: str, message: str, level: str = 'INFO', metadata: Dict = None) -> bool:
        """Logger un événement système"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO system_logs (
                        agent_name, message, level, timestamp, metadata
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    agent_name,
                    message,
                    level,
                    time.time(),
                    json.dumps(metadata or {})
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"❌ Erreur log système: {str(e)}")
            return False
    
    def get_system_logs(self, limit: int = 100, agent_name: str = None) -> List[Dict[str, Any]]:
        """Récupérer les logs système"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                if agent_name:
                    cursor.execute('''
                        SELECT * FROM system_logs 
                        WHERE agent_name = ? 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    ''', (agent_name, limit))
                else:
                    cursor.execute('''
                        SELECT * FROM system_logs 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    ''', (limit,))
                
                rows = cursor.fetchall()
                
                logs = []
                for row in rows:
                    log = {
                        'id': row['id'],
                        'agent_name': row['agent_name'],
                        'message': row['message'],
                        'level': row['level'],
                        'timestamp': row['timestamp'],
                        'metadata': json.loads(row['metadata']) if row['metadata'] else {}
                    }
                    logs.append(log)
                
                return logs
                
        except Exception as e:
            print(f"❌ Erreur récupération logs: {str(e)}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtenir les statistiques de la base de données"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # Compter les glyphs
                cursor.execute('SELECT COUNT(*) FROM glyphs')
                stats['total_glyphs'] = cursor.fetchone()[0]
                
                # Compter les concepts NOUS
                cursor.execute('SELECT COUNT(*) FROM nous_concepts')
                stats['total_nous_concepts'] = cursor.fetchone()[0]
                
                # Compter les découvertes ArXiv
                cursor.execute('SELECT COUNT(*) FROM arxiv_discoveries')
                stats['total_arxiv_discoveries'] = cursor.fetchone()[0]
                
                # Compter les logs
                cursor.execute('SELECT COUNT(*) FROM system_logs')
                stats['total_logs'] = cursor.fetchone()[0]
                
                # Agents les plus actifs
                cursor.execute('''
                    SELECT agent_name, COUNT(*) as count 
                    FROM glyphs 
                    GROUP BY agent_name 
                    ORDER BY count DESC 
                    LIMIT 5
                ''')
                stats['most_active_agents'] = dict(cursor.fetchall())
                
                return stats
                
        except Exception as e:
            print(f"❌ Erreur récupération stats: {str(e)}")
            return {}

# Instance globale
_storage_instance = None

def get_persistent_storage() -> PersistentStorage:
    """Obtenir l'instance de stockage persistant (singleton)"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = PersistentStorage()
    return _storage_instance

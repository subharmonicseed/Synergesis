"""
Neo4j Service for Archon Autonomous Agents
=========================================
Integration layer for persistent knowledge storage using Neo4j.
This provides the glyph bus persistence and knowledge accumulation
for the autonomous agent system.
"""

import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from neo4j import GraphDatabase
from pydantic import BaseModel

logger = logging.getLogger("Neo4jService")

class GlyphNode(BaseModel):
    """Neo4j node representation of a glyph."""
    id: str
    type: str
    source: str
    timestamp: str
    content: str
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

class Neo4jService:
    """Service for Neo4j interactions with autonomous agents."""
    
    def __init__(self):
        self.driver = None
        self._connect()
    
    def _connect(self):
        """Connect to Neo4j database."""
        try:
            uri = os.getenv('NEO4J_URI', 'bolt://neo4j:7687')
            user = os.getenv('NEO4J_USER', 'neo4j')
            password = os.getenv('NEO4J_PASSWORD', 'password')
            
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            logger.info("✅ Connected to Neo4j for autonomous agent service")
            
            # Ensure schema exists
            self._ensure_schema()
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Neo4j: {e}")
            raise
    
    def _ensure_schema(self):
        """Ensure the required schema exists."""
        with self.driver.session() as session:
            # Create constraints and indexes
            session.run("""
                CREATE CONSTRAINT glyph_id IF NOT EXISTS
                FOR (g:Glyph) REQUIRE g.id IS UNIQUE
            """)
            
            session.run("""
                CREATE INDEX glyph_type IF NOT EXISTS
                FOR (g:Glyph) ON (g.type)
            """)
            
            session.run("""
                CREATE INDEX glyph_source IF NOT EXISTS
                FOR (g:Glyph) ON (g.source)
            """)
            
            session.run("""
                CREATE INDEX glyph_timestamp IF NOT EXISTS
                FOR (g:Glyph) ON (g.timestamp)
            """)
            
            logger.info("✅ Neo4j schema initialized for autonomous agents")
    
    async def store_glyph(self, glyph) -> bool:
        """Store a glyph as a Neo4j node."""
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MERGE (g:Glyph {id: $id})
                    SET g.type = $type,
                        g.source = $source,
                        g.timestamp = $timestamp,
                        g.content = $content,
                        g.metadata = $metadata,
                        g.created_at = datetime(),
                        g.updated_at = datetime()
                    RETURN g
                """, 
                id=getattr(glyph, 'id', f"glyph_{datetime.now().timestamp()}"),
                type=getattr(glyph, 'type', 'unknown'),
                source=getattr(glyph, 'source', 'unknown'),
                timestamp=getattr(glyph, 'timestamp', datetime.now().isoformat()),
                content=getattr(glyph, 'content', ''),
                metadata=getattr(glyph, 'metadata', {})
                )
                
                logger.debug(f"✅ Stored glyph: {getattr(glyph, 'type', 'unknown')}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to store glyph: {e}")
            return False
    
    async def get_glyphs(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve glyphs from Neo4j."""
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (g:Glyph)
                    RETURN g.id as id, g.type as type, g.source as source,
                           g.timestamp as timestamp, g.content as content,
                           g.metadata as metadata
                    ORDER BY g.created_at DESC
                    SKIP $offset LIMIT $limit
                """, offset=offset, limit=limit)
                
                glyphs = []
                for record in result:
                    glyphs.append(dict(record))
                
                return glyphs
                
        except Exception as e:
            logger.error(f"❌ Failed to retrieve glyphs: {e}")
            return []
    
    async def get_glyphs_by_type(self, glyph_type: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve glyphs by type."""
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (g:Glyph {type: $type})
                    RETURN g.id as id, g.type as type, g.source as source,
                           g.timestamp as timestamp, g.content as content,
                           g.metadata as metadata
                    ORDER BY g.created_at DESC
                    LIMIT $limit
                """, type=glyph_type, limit=limit)
                
                glyphs = []
                for record in result:
                    glyphs.append(dict(record))
                
                return glyphs
                
        except Exception as e:
            logger.error(f"❌ Failed to retrieve glyphs by type: {e}")
            return []
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get system metrics from Neo4j."""
        try:
            with self.driver.session() as session:
                # Count total glyphs
                total_result = session.run("MATCH (g:Glyph) RETURN count(g) as total")
                total = total_result.single()['total']
                
                # Count by type
                type_result = session.run("""
                    MATCH (g:Glyph)
                    RETURN g.type as type, count(g) as count
                    ORDER BY count DESC
                """)
                
                type_counts = {}
                for record in type_result:
                    type_counts[record['type']] = record['count']
                
                return {
                    'total_glyphs': total,
                    'type_counts': type_counts,
                    'last_updated': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to get system metrics: {e}")
            return {'total_glyphs': 0, 'type_counts': {}}
    
    async def search_glyphs(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search glyphs by content."""
        try:
            with self.driver.session() as session:
                result = session.run("""
                    CALL db.index.fulltext.queryNodes('glyph_content', $query)
                    YIELD node, score
                    RETURN node.id as id, node.type as type, node.source as source,
                           node.timestamp as timestamp, node.content as content,
                           node.metadata as metadata, score
                    ORDER BY score DESC
                    LIMIT $limit
                """, query=query, limit=limit)
                
                glyphs = []
                for record in result:
                    glyphs.append(dict(record))
                
                return glyphs
                
        except Exception as e:
            logger.error(f"❌ Failed to search glyphs: {e}")
            return []
    
    async def close(self):
        """Close the Neo4j connection."""
        if self.driver:
            self.driver.close()
            logger.info("✅ Neo4j connection closed")
    
    def __del__(self):
        """Cleanup on destruction."""
        self.close()

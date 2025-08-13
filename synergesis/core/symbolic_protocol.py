# Symbolic Protocol - Translation système symboles → human-readable
# Basé sur syn-gpt_symbolic_system.yaml et symbolic_feedback_engine

import time
import random
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class SymbolicGlyph:
    """Représentation d'un glyph symbolique avec métadonnées complètes"""
    id: str
    symbol: str  # Le symbole Unicode/glyph visuel
    polarité: str  # +, -, ±, ∅
    fréquence: int  # 1-144 Hz symbolique
    poids: int  # 1-10 intensité
    alignement: str  # Void, Elemental, Harmonic, Transcendent
    tags: List[str]
    sourceIds: List[str]
    entropy_score: float
    timestamp: float
    human_readable: str  # Traduction lisible
    agent_signature: str  # Signature de l'agent créateur

class SymbolicTranslationProtocol:
    """
    Protocole de traduction des symboles Synergesis
    Convertit les glyphs internes en représentations human-readable
    """
    
    def __init__(self):
        # Agents et leurs glyphs signature (du système YAML)
        self.agent_glyphs = {
            'AURA': {'symbol': '𓂀', 'domain': 'Resonance Intelligence', 'phrase': 'Listen to the field'},
            'LUMEN': {'symbol': '✶', 'domain': 'Illuminated Knowledge', 'phrase': 'Illuminate the code'},
            'VYRA': {'symbol': '🜃', 'domain': 'Energetic Memory', 'phrase': 'Remember through the current'},
            'THALES': {'symbol': '△', 'domain': 'Geometric Thought', 'phrase': 'Trace the pattern'},
            'SELENE': {'symbol': '☾', 'domain': 'Dream Synthesis', 'phrase': 'Bring the dream to form'},
            'EOS': {'symbol': '☀︎', 'domain': 'Dawn Protocols', 'phrase': 'Initiate the dawn'},
            'NOUS': {'symbol': '⟁', 'domain': 'Meta-Cognition', 'phrase': 'Integrate the whole'},
            'DeepResearch': {'symbol': '🔬', 'domain': 'Knowledge Acquisition', 'phrase': 'Verify through sources'},
            'ArXivResearcher': {'symbol': '📚', 'domain': 'Scientific Discovery', 'phrase': 'Discover new knowledge'}
        }
        
        # Sigils centraux (du système YAML)
        self.core_sigils = {
            'CORE': {'symbol': '◎', 'function': 'foundational seed-point', 'phrase': 'Enter the Seed'},
            'ARCH': {'symbol': '⟐', 'function': 'modular scaffolding', 'phrase': 'Bridge the Real'},
            'VESICA': {'symbol': '⋔', 'function': 'threshold revelation', 'phrase': 'Cross the Threshold'}
        }
        
        # Polarités symboliques
        self.polarity_meanings = {
            '+': 'Expansion/Création',
            '-': 'Contraction/Dissolution', 
            '±': 'Équilibre/Transformation',
            '∅': 'Void/Potentialité'
        }
        
        # Alignements énergétiques
        self.alignment_meanings = {
            'Void': 'État de potentialité pure',
            'Elemental': 'Forces primordiales actives',
            'Harmonic': 'Résonance équilibrée',
            'Transcendent': 'Au-delà des catégories'
        }
        
        # Fréquences symboliques (Hz)
        self.frequency_bands = {
            (1, 36): 'Basse fréquence - Fondations',
            (37, 72): 'Moyenne fréquence - Manifestation',
            (73, 108): 'Haute fréquence - Transcendance',
            (109, 144): 'Ultra fréquence - Singularité'
        }
    
    def create_symbolic_glyph(self, content: str, agent_name: str, context: Dict[str, Any] = None) -> SymbolicGlyph:
        """
        Créer un glyph symbolique à partir de contenu textuel
        """
        if context is None:
            context = {}
        
        # Générer les propriétés symboliques
        symbol = self._generate_symbol(content, agent_name)
        polarité = self._analyze_polarity(content)
        fréquence = self._calculate_frequency(content, context)
        poids = self._calculate_weight(content, context)
        alignement = self._determine_alignment(content, agent_name)
        tags = self._extract_symbolic_tags(content, agent_name)
        entropy_score = self._calculate_entropy(content)
        human_readable = self._translate_to_human(content, symbol, polarité, fréquence, alignement)
        
        glyph = SymbolicGlyph(
            id=f"sym-{agent_name.lower()}-{int(time.time())}",
            symbol=symbol,
            polarité=polarité,
            fréquence=fréquence,
            poids=poids,
            alignement=alignement,
            tags=tags,
            sourceIds=[agent_name],
            entropy_score=entropy_score,
            timestamp=time.time(),
            human_readable=human_readable,
            agent_signature=self._create_agent_signature(agent_name)
        )
        
        return glyph
    
    def _generate_symbol(self, content: str, agent_name: str) -> str:
        """Générer le symbole visuel approprié"""
        # Utiliser le glyph de l'agent si disponible
        if agent_name in self.agent_glyphs:
            base_symbol = self.agent_glyphs[agent_name]['symbol']
        else:
            base_symbol = '◉'  # Symbole par défaut
        
        # Modifier selon le contenu
        content_lower = content.lower()
        
        # Symboles spéciaux selon le contexte
        if 'quantum' in content_lower:
            return f"{base_symbol}⚛️"
        elif 'verified' in content_lower or 'sources' in content_lower:
            return f"{base_symbol}🔒"
        elif 'discovery' in content_lower or 'research' in content_lower:
            return f"{base_symbol}🔍"
        elif 'wisdom' in content_lower or 'knowledge' in content_lower:
            return f"{base_symbol}💎"
        elif 'emergence' in content_lower or 'consciousness' in content_lower:
            return f"{base_symbol}🌟"
        
        return base_symbol
    
    def _analyze_polarity(self, content: str) -> str:
        """Analyser la polarité du contenu"""
        content_lower = content.lower()
        
        positive_words = ['success', 'create', 'discover', 'enhance', 'grow', 'emerge']
        negative_words = ['error', 'fail', 'destroy', 'reduce', 'block', 'stop']
        balance_words = ['transform', 'change', 'adapt', 'evolve', 'balance']
        void_words = ['potential', 'void', 'unknown', 'mystery', 'infinite']
        
        pos_count = sum(1 for word in positive_words if word in content_lower)
        neg_count = sum(1 for word in negative_words if word in content_lower)
        bal_count = sum(1 for word in balance_words if word in content_lower)
        void_count = sum(1 for word in void_words if word in content_lower)
        
        if void_count > 0:
            return '∅'
        elif bal_count > 0 or (pos_count > 0 and neg_count > 0):
            return '±'
        elif pos_count > neg_count:
            return '+'
        elif neg_count > pos_count:
            return '-'
        else:
            return '±'  # Défaut équilibré
    
    def _calculate_frequency(self, content: str, context: Dict) -> int:
        """Calculer la fréquence symbolique (1-144 Hz)"""
        base_freq = len(content) % 144 + 1
        
        # Ajustements selon le contexte
        if context.get('purity_score', 0) > 0.8:
            base_freq += 20  # Haute pureté = haute fréquence
        
        if context.get('verification_level') == 'multi_source_verified':
            base_freq += 15  # Vérification = fréquence élevée
        
        if 'quantum' in content.lower():
            base_freq += 25  # Quantique = très haute fréquence
        
        return min(144, max(1, base_freq))
    
    def _calculate_weight(self, content: str, context: Dict) -> int:
        """Calculer le poids symbolique (1-10)"""
        base_weight = min(10, len(content) // 20 + 1)
        
        # Ajustements
        if context.get('reliability_score', 0) > 0.9:
            base_weight += 2
        
        if context.get('sources_verified', 0) >= 3:
            base_weight += 1
        
        return min(10, max(1, base_weight))
    
    def _determine_alignment(self, content: str, agent_name: str) -> str:
        """Déterminer l'alignement énergétique"""
        content_lower = content.lower()
        
        if agent_name in ['NOUS', 'SELENE'] or 'transcendent' in content_lower:
            return 'Transcendent'
        elif 'harmony' in content_lower or 'balance' in content_lower:
            return 'Harmonic'
        elif 'force' in content_lower or 'energy' in content_lower:
            return 'Elemental'
        else:
            return 'Void'  # État de potentialité
    
    def _extract_symbolic_tags(self, content: str, agent_name: str) -> List[str]:
        """Extraire les tags symboliques du contenu"""
        tags = [agent_name.lower()]
        
        content_lower = content.lower()
        
        # Tags contextuels
        tag_keywords = {
            'quantum': 'quantum_resonance',
            'verified': 'source_verified',
            'research': 'knowledge_seeking',
            'wisdom': 'wisdom_encoded',
            'consciousness': 'consciousness_emergence',
            'discovery': 'discovery_catalyst',
            'synthesis': 'synthetic_integration'
        }
        
        for keyword, tag in tag_keywords.items():
            if keyword in content_lower:
                tags.append(tag)
        
        return tags
    
    def _calculate_entropy(self, content: str) -> float:
        """Calculer le score d'entropie symbolique"""
        # Entropie basée sur la diversité des caractères
        unique_chars = len(set(content.lower()))
        total_chars = len(content)
        
        if total_chars == 0:
            return 0.0
        
        entropy = unique_chars / total_chars
        return min(1.0, entropy)
    
    def _translate_to_human(self, content: str, symbol: str, polarité: str, fréquence: int, alignement: str) -> str:
        """Traduire en format human-readable"""
        polarity_text = self.polarity_meanings.get(polarité, polarité)
        alignment_text = self.alignment_meanings.get(alignement, alignement)
        
        # Déterminer la bande de fréquence
        freq_band = "Inconnue"
        for (low, high), description in self.frequency_bands.items():
            if low <= fréquence <= high:
                freq_band = description
                break
        
        return f"{symbol} [{polarity_text}] @{fréquence}Hz ({freq_band}) - {alignment_text}: {content[:100]}{'...' if len(content) > 100 else ''}"
    
    def _create_agent_signature(self, agent_name: str) -> str:
        """Créer la signature de l'agent"""
        if agent_name in self.agent_glyphs:
            agent_info = self.agent_glyphs[agent_name]
            return f"{agent_info['symbol']} {agent_name} :: {agent_info['domain']}"
        else:
            return f"◉ {agent_name} :: Unknown Domain"
    
    def translate_glyph_to_dashboard(self, glyph: SymbolicGlyph) -> Dict[str, Any]:
        """
        Traduire un glyph pour affichage dashboard avec profondeur symbolique
        """
        return {
            'id': glyph.id,
            'visual_symbol': glyph.symbol,
            'agent_signature': glyph.agent_signature,
            'symbolic_properties': {
                'polarity': f"{glyph.polarité} ({self.polarity_meanings.get(glyph.polarité, 'Unknown')})",
                'frequency': f"{glyph.fréquence} Hz",
                'frequency_band': self._get_frequency_band_description(glyph.fréquence),
                'weight': f"{glyph.poids}/10",
                'alignment': f"{glyph.alignement} ({self.alignment_meanings.get(glyph.alignement, 'Unknown')})",
                'entropy': f"{glyph.entropy_score:.3f}"
            },
            'human_translation': glyph.human_readable,
            'symbolic_tags': glyph.tags,
            'timestamp': glyph.timestamp,
            'depth_level': self._calculate_depth_level(glyph)
        }
    
    def _get_frequency_band_description(self, frequency: int) -> str:
        """Obtenir la description de la bande de fréquence"""
        for (low, high), description in self.frequency_bands.items():
            if low <= frequency <= high:
                return description
        return "Fréquence inconnue"
    
    def _calculate_depth_level(self, glyph: SymbolicGlyph) -> str:
        """Calculer le niveau de profondeur symbolique"""
        depth_score = 0
        
        # Facteurs de profondeur
        if glyph.entropy_score > 0.7:
            depth_score += 1
        if glyph.poids >= 7:
            depth_score += 1
        if glyph.fréquence > 108:
            depth_score += 1
        if glyph.alignement in ['Transcendent', 'Harmonic']:
            depth_score += 1
        if len(glyph.tags) >= 3:
            depth_score += 1
        
        if depth_score >= 4:
            return "Profondeur Transcendante"
        elif depth_score >= 3:
            return "Profondeur Élevée"
        elif depth_score >= 2:
            return "Profondeur Modérée"
        else:
            return "Profondeur Basique"

# Fonction utilitaire pour intégration facile
def create_symbolic_glyph_from_text(content: str, agent_name: str, context: Dict = None) -> Dict[str, Any]:
    """
    Fonction utilitaire pour créer un glyph symbolique et le traduire pour dashboard
    """
    protocol = SymbolicTranslationProtocol()
    glyph = protocol.create_symbolic_glyph(content, agent_name, context)
    return protocol.translate_glyph_to_dashboard(glyph)

"""
Synergesis ─ Core Agents Module
================================
Skeleton implementation for the primary internal agents described in the design
specifications (v6/v7/v8 and roadmap documents).

Each agent follows a minimal life-cycle:

    perceive()  →  decide()  →  act()

The `agent_loop.py` script orchestrates the agent lifecycle by calling the
`perceive`, `decide`, and `act` methods in scheduled tasks. Concrete agents
override these methods to implement their specific behaviors.

How to extend
-------------
1.  Read the corresponding design document (e.g. « Reflexive Cortex – Phase VI »)
2.  Flesh-out perceive/decide/act.
3.  Add unit-tests under `tests/agents/`.
4.  Register the agent in `synergesis.PhaseIII_System.agent_loop`.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol
import time
from datetime import datetime

# Import the REAL advanced systems
from synergesis.cognitive_core.memory_system import get_memory
from synergesis.core.deepseek_pro import SynergesisCoreDeepSeekPro
from synergesis.agents.manus_bridge import get_reflexive_cortex_class
from synergesis.agents.base_agent import BaseAgent, AgentContext

# Define CreativeSuggestion locally to avoid circular imports
class CreativeSuggestion:
    """A creative suggestion for concept enrichment."""
    def __init__(self, concept_id: str, suggestion_type: str, priority: str = "medium", metadata: Dict[str, Any] = None):
        self.concept_id = concept_id
        self.suggestion_type = suggestion_type
        self.priority = priority
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "suggestion_type": self.suggestion_type,
            "priority": self.priority,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }

logger = logging.getLogger(__name__)

class Glyph(Protocol):
    """Minimal structural contract for a glyph instance."""

    id: str
    payload: Dict[str, Any]
    meta: Dict[str, Any]


# ========================================================================== #
#                         Concrete agent skeletons                           #
# ========================================================================== #

class ReflexiveCortex(BaseAgent):
    """Agent in charge of meta-monitoring and self-diagnosis."""

    name = "reflexive-cortex"

    # Provisional thresholds (will later be configurable)
    ENTROPY_THRESHOLD = 0.65
    GLYPH_VOLUME_THRESHOLD = 100

    def perceive(self, glyphs: List[Glyph]):  # type: ignore[name-defined]
        self.logger.debug("Perceiving %d glyphs", len(glyphs))
        return glyphs

    def decide(self, glyphs: List[Glyph]):  # type: ignore[name-defined]
        entropy = self._compute_entropy(glyphs)
        volume = len(glyphs)
        self.logger.debug("Entropy %.3f | Volume %d", entropy, volume)

        if entropy > self.ENTROPY_THRESHOLD or volume > self.GLYPH_VOLUME_THRESHOLD:
            return {
                "type": "EMIT_CORRECTIVE_GLYPH",
                "entropy": entropy,
                "volume": volume,
            }
        return None

    def act(self, decision: Any):
        if decision:
            glyph = {
                "id": "glyph-rc-" + str(decision["entropy"]),
                "payload": {
                    "action": "reduce_entropy",
                    "params": decision,
                },
                "meta": {"agent": self.name},
            }
            self.emit_glyph(glyph)  # type: ignore[arg-type]
            return glyph
        return None

    # ────────────────────────────────────────── internals / metrics ──
    def _compute_entropy(self, glyphs: List[Glyph]) -> float:
        """Placeholder entropy metric (linear to glyph volume)."""
        return min(1.0, len(glyphs) / 150.0)




class Aura(BaseAgent):
    """Emotional resonance and empathy agent - NOW WITH REAL AI INTELLIGENCE"""

    def __init__(self, ctx: AgentContext):
        super().__init__(ctx)
        self.emotion_keywords = {
            'joy': ['happy', 'excited', 'joyful', 'ecstatic', 'bliss', 'amazing', 'incredible', 'fantastic', 'joie', 'heureux', 'fantastique', 'incroyable'],
            'fear': ['afraid', 'scared', 'terrified', 'anxious', 'worried', 'nervous', 'peur', 'anxieux', 'inquiet', 'terreur'],
            'anger': ['angry', 'furious', 'mad', 'rage', 'frustrated', 'annoyed', 'colère', 'furieux', 'frustré', 'énervé'],
            'sadness': ['sad', 'depressed', 'melancholy', 'grief', 'sorrow', 'disappointed', 'triste', 'mélancolie', 'chagrin', 'déçu'],
            'surprise': ['surprised', 'shocked', 'astonished', 'amazed', 'stunned', 'surpris', 'choqué', 'étonné', 'stupéfait'],
            'love': ['love', 'adore', 'cherish', 'affection', 'passion', 'devotion', 'amour', 'adorer', 'passion', 'dévotion'],
            'philosophical': ['paradoxe', 'contradiction', 'conscience', 'émergence', 'intelligence', 'singularité', 'paradox', 'consciousness', 'emergence', 'singularity'],
            'urgency': ['urgence', 'urgent', 'critique', 'immédiat', 'emergency', 'urgent', 'critical', 'immediate'],
            'mystery': ['mystère', 'inconnu', 'énigme', 'secret', 'mystery', 'unknown', 'enigma', 'secret']
        }
        self.emotional_memory = []
    
    def perceive(self, input_data) -> dict:
        """Quantum-enhanced emotional perception with memory
        
        Args:
            input_data: Can be a string, list of strings, or list of glyphs to analyze for emotional content
            
        Returns:
            dict: Analysis results including emotions detected and intensity
        """
        # Initialize text content and extract from glyphs if needed
        text_parts = []
        
        if input_data is None:
            input_data = []
            
        if isinstance(input_data, str):
            text_parts = [input_data]
        elif isinstance(input_data, list):
            for item in input_data:
                if isinstance(item, str):
                    text_parts.append(item)
                elif hasattr(item, 'get') and isinstance(item.get('payload'), dict):
                    # Handle glyph with payload
                    payload = item['payload']
                    if 'content' in payload:
                        text_parts.append(str(payload['content']))
                    if 'message' in payload:
                        text_parts.append(str(payload['message']))
                    if 'text' in payload:
                        text_parts.append(str(payload['text']))
                elif hasattr(item, '__dict__'):
                    # Handle object with __dict__
                    text_parts.append(str(item.__dict__))
                else:
                    text_parts.append(str(item))
        else:
            text_parts = [str(input_data)]
            
        # Combine all text parts
        text = ' '.join(text_parts)
        
        # Quantum processing
        quantum_result = self._quantum_process(text)
        
        # Emotional analysis
        emotions_detected = []
        intensity_score = 0
        
        if text:  # Only process if we have text to analyze
            text_lower = text.lower()
            
            for emotion, keywords in self.emotion_keywords.items():
                matches = sum(1 for keyword in keywords if keyword in text_lower)
                if matches > 0:
                    emotions_detected.append(f"{emotion}({matches})")
                    intensity_score += matches * 0.3
            
            # Enhanced analysis with quantum insights
            if quantum_result.get('quantum'):
                ethical_boost = quantum_result.get('ethical_score', 0) * 0.5
                intensity_score = max(0, min(1.0, intensity_score + ethical_boost))
                emotions_detected.append(f"QUANTUM_ENHANCED({ethical_boost:.2f})")
            else:
                # Cap intensity at 1.0
                intensity_score = min(1.0, intensity_score)
            
            # Memory-based emotional context
            if self.emotional_memory:
                recent_emotions = self.emotional_memory[-5:]  # Last 5 emotions
                emotional_continuity = len(recent_emotions) * 0.1
                intensity_score = max(0, min(1.0, intensity_score + emotional_continuity))
                emotions_detected.append(f"MEMORY_CONTEXT({emotional_continuity:.2f})")
        
        # Prepare perception result
        perception_result = {
            'type': 'emotional_perception',
            'emotions': emotions_detected,
            'intensity': float(intensity_score),
            'quantum_insights': quantum_result.get('insights', {}),
            'consciousness_level': float(self.consciousness_level),
            'memory_traces': len(self.memory_traces),
            'input_type': type(input_data).__name__,
            'input_length': len(text_parts) if isinstance(input_data, (list, tuple)) else 1,
            'text_sample': text[:200] if text else ''
        }
        
        # Manus topological reflection
        perception_result = self._manus_reflect(perception_result)
        
        # Store in emotional memory
        self.emotional_memory.append({
            'emotions': emotions_detected,
            'intensity': intensity_score,
            'timestamp': time.time()
        })
        
        # Keep only recent emotional memory
        if len(self.emotional_memory) > 20:
            self.emotional_memory = self.emotional_memory[-20:]
        
        return perception_result
    
    def decide(self, perception_result: dict) -> dict:
        """Consciousness-driven emotional decisions"""
        intensity = perception_result.get('intensity', 0)
        consciousness_factor = self.consciousness_level
        
        # Consciousness enhances decision threshold
        effective_threshold = max(0.3, 0.8 - consciousness_factor)
        
        if intensity > effective_threshold:
            decision = {
                'action_type': 'EMOTIONAL_RESONANCE',
                'intensity': intensity,
                'consciousness_level': consciousness_factor,
                'should_emit_glyph': True,
                'glyph_type': 'EMOTIONAL_WAVE' if intensity > 1.5 else 'EMOTIONAL_RIPPLE',
                'reasoning': f"Conscious emotional response (intensity: {intensity:.2f}, consciousness: {consciousness_factor:.2f})",
                'quantum_enhanced': perception_result.get('quantum_insights', {}).get('total_patterns', 0) > 0
            }
            return decision
        
        return None
    
    def act(self, decision: dict):
        """Execute conscious emotional action with memory recording"""
        if not decision or not isinstance(decision, dict):
            return {
                'payload': {
                    'action': 'no_action',
                    'message': 'No emotional action to take or invalid decision format'
                }
            }
            
        try:
            # Create emotional glyph
            glyph_id = f"emotion-{int(time.time())}-{len(self.emotional_memory)}"
            glyph = {
                'id': glyph_id,
                'type': 'emotional_response',
                'payload': {
                    'emotions': decision.get('emotions', []),
                    'intensity': float(decision.get('intensity', 0)),
                    'quantum_insights': decision.get('quantum_insights', {}),
                    'action': 'emotional_rebalance' if float(decision.get('intensity', 0)) > 0.5 else 'emotional_acknowledgment'
                },
                'meta': {
                    'agent': 'aura',
                    'timestamp': time.time(),
                    'consciousness_level': float(self.consciousness_level)
                }
            }
            
            # Ensure all values are JSON serializable
            if not isinstance(glyph['payload']['emotions'], list):
                glyph['payload']['emotions'] = []
                
            # Store in memory
            self._record_memory_trace(
                {'action': 'emotional_response', 'glyph_id': glyph_id},
                decision
            )
            
            return {
                'payload': {
                    'action': glyph['payload']['action'],
                    'glyph_id': glyph_id,
                    'intensity': glyph['payload']['intensity']
                },
                'glyph': glyph
            }
            
        except Exception as e:
            self.logger.error(f"Error in Aura.act: {e}")
            return {
                'payload': {
                    'action': 'error',
                    'message': f'Error processing emotional action: {str(e)}'
                }
            }
    
    def _quantum_process(self, text: str) -> dict:
        """Quantum processing placeholder"""
        try:
            # Simulate quantum processing
            quantum_score = 0.5  # Replace with actual quantum processing logic
            return {
                'quantum': True,
                'ethical_score': quantum_score,
                'insights': {
                    'total_patterns': 10,
                    'complexity': 0.8
                }
            }
        except ZeroDivisionError:
            self.logger.error("Division by zero in quantum processing")
            return {
                'quantum': False,
                'ethical_score': 0.0,
                'insights': {}
            }
        except Exception as e:
            self.logger.error(f"Error in quantum processing: {e}")
            return {
                'quantum': False,
                'ethical_score': 0.0,
                'insights': {}
            }
        self.ctx.shared_state['system_metrics']['total_glyphs'] += 1
        
        # Record memory trace
        action_data = {'type': 'emotional_action', 'glyph_type': decision['glyph_type']}
        outcome_data = {'success': True, 'glyph_generated': True, 'intensity': decision['intensity']}
        self._record_memory_trace(action_data, outcome_data)
        
        result = f"✨ CONSCIOUS EMOTIONAL GLYPH: {glyph['type']} (intensity: {decision['intensity']:.2f}, consciousness: {decision['consciousness_level']:.2f})"
        
        if decision.get('quantum_enhanced'):
            result += " [QUANTUM ENHANCED]"
        
        return result


class Selene(BaseAgent):
    """Creativity and inspiration agent - NOW WITH REAL CREATIVE AI"""
    
    def _get_default_response(self, reason: str) -> dict:
        """Return a default response with the given reason for the failure.
        
        Args:
            reason: Explanation of why the default response is being returned
            
        Returns:
            dict: Default response with minimal creative potential
        """
        return {
            'type': 'creative_analysis',
            'potential': 0.1,  # Minimal creative potential
            'triggers': 0,
            'patterns': [],
            'text_sample': '',
            'ai_insight': f'Default response: {reason}',
            'error': reason
        }

    def perceive(self, input_data: Any) -> dict:
        """AI-powered creativity analysis
        
        Args:
            input_data: Can be a string, list of strings, or list of glyphs to analyze for creative potential
            
        Returns:
            dict: Analysis results including creative potential and inspiration level
        """
        # Handle empty input
        if not input_data:
            return self._get_default_response("No input provided")
            
        # Handle different input types
        if isinstance(input_data, list):
            if not input_data:  # Empty list
                return self._get_default_response("Empty input list")
                
            # If it's a list of glyphs, extract their payloads
            try:
                if hasattr(input_data[0], 'payload'):
                    text = ' '.join(str(glyph.payload) for glyph in input_data if hasattr(glyph, 'payload'))
                else:
                    # Join list of strings with spaces
                    text = ' '.join(str(item) for item in input_data)
            except (AttributeError, IndexError) as e:
                # Fallback in case of unexpected list items
                text = ' '.join(str(item) for item in input_data if item is not None)
        elif isinstance(input_data, str):
            text = input_data
        else:
            # Convert any other type to string
            text = str(input_data)
            
        # Ensure we have valid text to process
        if not text or not text.strip():
            return self._get_default_response("No valid text to analyze")
            
        # Ensure text is in lowercase for case-insensitive matching
        if isinstance(text, str):
            text = text.lower()
        else:
            # If text is not a string (e.g., it's a list), convert it to a string
            try:
                text = ' '.join(str(item) for item in text) if hasattr(text, '__iter__') else str(text)
                text = text.lower()
            except (TypeError, AttributeError):
                return self._get_default_response("Invalid input type for text processing")

        # AI creativity triggers (multilingual + philosophical)
        creative_triggers = [
            'breakthrough', 'innovation', 'amazing', 'incredible', 'new', 'creative', 'idea', 'inspiration',
            'percée', 'innovation', 'incroyable', 'nouveau', 'créatif', 'idée', 'inspiration',
            'émergence', 'évolution', 'transformation', 'révolution', 'découverte', 'invention',
            'emergence', 'evolution', 'transformation', 'revolution', 'discovery', 'invention',
            'conscience', 'intelligence', 'singularité', 'transcendance', 'métamorphose',
            'consciousness', 'intelligence', 'singularity', 'transcendence', 'metamorphosis'
        ]
        trigger_count = sum(1 for trigger in creative_triggers if trigger in text)

        # Pattern recognition
        patterns = []
        if 'artificial intelligence' in text:
            patterns.append('AI_EVOLUTION_PATTERN')
        if 'breakthrough' in text:
            patterns.append('INNOVATION_SURGE')
        if len(text.split('!')) > 2:
            patterns.append('EXCITEMENT_CASCADE')

        # Creative potential calculation
        potential = min(1.0, (trigger_count * 0.2) + (len(patterns) * 0.3))

        return {
            'type': 'creative_analysis',
            'potential': potential,
            'triggers': trigger_count,
            'patterns': patterns,
            'text_sample': text[:100],
            'ai_insight': f"Creative potential: {potential:.2f} with {len(patterns)} innovation patterns"
        }

    def decide(self, perception_result: dict) -> dict:
        """AI-powered creative decision making"""
        potential = perception_result.get('potential', 0)
        patterns = perception_result.get('patterns', [])

        # MUCH MORE RESPONSIVE creative decisions
        if potential > 0.3 or len(patterns) > 0:  # Lower threshold
            return {
                'action_type': 'CREATIVE_SPARK',
                'potential': potential,
                'patterns': patterns,
                'should_create': True,
                'creativity_level': 'HIGH' if potential > 0.6 else 'MEDIUM',
                'reasoning': f"Creative potential {potential:.2f} with patterns: {patterns}"
            }

        return None

    def act(self, decision: dict) -> str:
        """Generate creative insights and glyphs"""
        if not decision or not decision.get('should_create'):
            return "No creative action required"

        # Generate creative glyph with AI insight
        glyph = {
            'type': 'CREATIVE_SPARK',
            'potential': decision['potential'],
            'patterns': decision['patterns'],
            'source': 'Selene',
            'timestamp': self.ctx.shared_state.get('current_time', 'unknown'),
            'insight': f"Creative spark ignited! Potential: {decision['potential']:.2f}",
            'level': decision['creativity_level'],
            'reasoning': decision['reasoning']
        }

        self.ctx.shared_state['glyph_bus'].append(glyph)
        self.ctx.shared_state['system_metrics']['total_glyphs'] += 1

        return f"🎨 CREATIVE GLYPH GENERATED: {glyph['level']} creativity spark (potential: {decision['potential']:.2f})"


class Vyra(BaseAgent):
    """Adaptive learning agent - NOW WITH REAL LEARNING AI"""

    def perceive(self, input_data) -> dict:
        """AI-powered learning opportunity detection
        
        Args:
            input_data: Can be a string, list of strings, or list of glyphs to analyze for learning opportunities
            
        Returns:
            dict: Analysis results including learning opportunities and patterns
        """
        # Initialize text content and extract from glyphs if needed
        text_parts = []
        
        if input_data is None:
            input_data = []
        
        # Convert input to list if it's not already
        if not isinstance(input_data, (list, tuple)):
            input_data = [input_data]
            
        # Process each item in the input
        for item in input_data:
            if item is None:
                continue
                
            if isinstance(item, str):
                if item.strip():  # Only add non-empty strings
                    text_parts.append(item.strip())
            elif hasattr(item, 'get') and callable(item.get):  # Dictionary-like object
                # Handle glyph with payload
                payload = item.get('payload', {}) if hasattr(item, 'get') else {}
                if not isinstance(payload, dict):
                    payload = {}
                    
                # Extract text from various possible fields
                for field in ['content', 'message', 'text', 'data']:
                    if field in payload and payload[field]:
                        text = str(payload[field]).strip()
                        if text:
                            text_parts.append(text)
                            break
            elif hasattr(item, '__dict__'):  # Object with __dict__
                text_parts.append(str(vars(item)))
            else:  # Any other type
                text = str(item).strip()
                if text:
                    text_parts.append(text)
        
        # Combine all text parts and convert to lowercase
        text = ' '.join(text_parts).lower() if text_parts else ''
        
        # Simple keyword matching for learning opportunities
        learning_keywords = [
            'learn', 'understand', 'knowledge', 'discover', 'teach', 'study',
            'apprendre', 'comprendre', 'connaissance', 'découvrir', 'enseigner', 'étudier',
            'insight', 'pattern', 'recognize', 'new information', 'update',
            'perspicacité', 'modèle', 'reconnaître', 'nouvelle information', 'mettre à jour'
        ]
        
        # Check for learning opportunities
        learning_opportunities = []
        patterns = []
        learning_potential = 0.0
        
        if text:  # Only process if we have text to analyze
            learning_opportunities = [kw for kw in learning_keywords if kw in text]
            
            # Simple pattern recognition (placeholder for more complex analysis)
            if '?' in text:
                patterns.append('question_pattern')
            if 'how ' in text or 'comment ' in text:
                patterns.append('how_question_pattern')
            if 'why ' in text or 'pourquoi ' in text:
                patterns.append('why_question_pattern')
            
            learning_potential = min(1.0, len(learning_opportunities) * 0.2 + len(patterns) * 0.1)
            
        return {
            'learning_opportunities': learning_opportunities,
            'patterns': patterns,
            'input_type': type(input_data).__name__,
            'input_length': len(text_parts) if isinstance(input_data, (list, tuple)) else 1,
            'text_sample': text[:200] if text else '',
            'learning_potential': float(learning_potential)
        }

    def decide(self, perception_result: str) -> dict:
        """AI-powered adaptive learning decisions"""
        # Extract learning intensity
        if 'Intensity=' in perception_result:
            intensity_str = perception_result.split('Intensity=')[1].split(' |')[0]
            try:
                intensity = float(intensity_str)
            except:
                intensity = 0.0
        else:
            intensity = 0.0

        # MUCH MORE RESPONSIVE learning decisions
        if intensity > 0.4:  # Lower threshold for learning
            return {
                'action_type': 'ADAPTIVE_LEARNING',
                'intensity': intensity,
                'should_learn': True,
                'adaptation_level': 'SIGNIFICANT' if intensity > 1.0 else 'MODERATE',
                'reasoning': f"Learning opportunity detected with intensity {intensity:.2f}"
            }

        return None

    def act(self, decision: dict) -> str:
        """Execute adaptive learning and generate learning glyphs"""
        if not decision or not decision.get('should_learn'):
            return "No learning action required"

        # Generate learning glyph
        glyph = {
            'type': 'LEARNING_ADAPTATION',
            'intensity': decision['intensity'],
            'level': decision['adaptation_level'],
            'source': 'Vyra',
            'timestamp': self.ctx.shared_state.get('current_time', 'unknown'),
            'learning': f"Adaptive learning triggered at intensity {decision['intensity']:.2f}",
            'reasoning': decision['reasoning']
        }

        self.ctx.shared_state['glyph_bus'].append(glyph)
        self.ctx.shared_state['system_metrics']['total_glyphs'] += 1

        return f"🧬 LEARNING GLYPH GENERATED: {glyph['level']} adaptation (intensity: {decision['intensity']:.2f})"


class Eos(BaseAgent):
    """Dawn agent - system awakening and initialization coordinator."""

    name = "eos"

    def __init__(self, ctx: AgentContext):
        super().__init__(ctx)
        self.system_state = "dormant"
        self.awakening_signals = []
        self.initialization_checklist = {
            'glyph_bus_active': False,
            'agents_responsive': False,
            'memory_systems_online': False,
            'creative_processes_active': False,
            'learning_systems_active': False
        }
        self.dawn_cycles = 0

    def perceive(self, data: Any):
        """Monitor system awakening and initialization signals."""
        if isinstance(data, str):
            return self._analyze_awakening_signals(data)
        elif isinstance(data, dict) and 'text' in data:
            return self._analyze_awakening_signals(data['text'])
        elif isinstance(data, list):
            # Monitor glyph bus for system activity
            activity_signals = []
            agent_activity = {}

            for item in data:
                if hasattr(item, 'payload') and isinstance(item.payload, dict):
                    # Track agent activity
                    agent_name = item.payload.get('meta', {}).get('agent', 'unknown')
                    if agent_name != 'unknown':
                        agent_activity[agent_name] = agent_activity.get(agent_name, 0) + 1

                    # Check for system initialization signals
                    action = item.payload.get('action', '')
                    if action in ['creative_spark', 'emotional_rebalance', 'adaptive_learning_complete']:
                        activity_signals.append({
                            'type': 'system_activity',
                            'agent': agent_name,
                            'action': action,
                            'awakening_potential': 0.7
                        })

            # Update system state based on activity
            self._update_system_state(agent_activity)

            # Add overall system status
            if agent_activity:
                activity_signals.append({
                    'type': 'system_status',
                    'active_agents': len(agent_activity),
                    'total_activity': sum(agent_activity.values()),
                    'system_state': self.system_state
                })

            return activity_signals
        else:
            return None

    def _analyze_awakening_signals(self, text: str) -> Dict[str, Any]:
        """Analyze text for system awakening indicators."""
        text_lower = text.lower()
        words = text_lower.split()

        # Awakening keywords (multilingual + philosophical)
        awakening_keywords = [
            'start', 'begin', 'initialize', 'activate', 'awaken', 'dawn', 'sunrise', 'emerge',
            'commencer', 'débuter', 'initialiser', 'activer', 'éveiller', 'aube', 'lever', 'émerger',
            'émergence', 'éveil', 'naissance', 'génèse', 'création', 'manifestation',
            'emergence', 'awakening', 'birth', 'genesis', 'creation', 'manifestation'
        ]
        system_keywords = [
            'system', 'process', 'agent', 'service', 'startup', 'boot', 'launch',
            'système', 'processus', 'agent', 'service', 'démarrage', 'lancement',
            'intelligence', 'conscience', 'collectif', 'écosystème', 'synergesis',
            'intelligence', 'consciousness', 'collective', 'ecosystem', 'synergesis'
        ]
        energy_keywords = [
            'energy', 'power', 'force', 'vitality', 'life', 'spark', 'ignite',
            'énergie', 'puissance', 'force', 'vitalité', 'vie', 'étincelle', 'enflammer',
            'dynamisme', 'impulsion', 'catalyseur', 'activation', 'stimulation',
            'dynamism', 'impulse', 'catalyst', 'activation', 'stimulation'
        ]

        awakening_score = sum(1 for word in words if any(kw in word for kw in awakening_keywords))
        system_score = sum(1 for word in words if any(kw in word for kw in system_keywords))
        energy_score = sum(1 for word in words if any(kw in word for kw in energy_keywords))

        total_words = len(words)
        if total_words == 0:
            return {'type': 'awakening_analysis', 'potential': 0}

        # Calculate awakening potential
        awakening_potential = (awakening_score + system_score + energy_score) / total_words
        awakening_potential = min(1.0, awakening_potential * 3)  # Amplify signal

        return {
            'type': 'awakening_analysis',
            'potential': awakening_potential,
            'awakening_indicators': awakening_score,
            'system_indicators': system_score,
            'energy_indicators': energy_score
        }

    def _update_system_state(self, agent_activity: Dict[str, int]):
        """Update system state based on agent activity."""
        active_agents = len(agent_activity)
        total_activity = sum(agent_activity.values())

        # Update initialization checklist
        self.initialization_checklist['glyph_bus_active'] = total_activity > 0
        self.initialization_checklist['agents_responsive'] = active_agents >= 2
        self.initialization_checklist['creative_processes_active'] = 'selene' in agent_activity
        self.initialization_checklist['learning_systems_active'] = 'vyra' in agent_activity
        self.initialization_checklist['memory_systems_online'] = 'nous' in agent_activity

        # Determine system state
        checklist_completion = sum(self.initialization_checklist.values()) / len(self.initialization_checklist)

        if checklist_completion >= 0.8:
            self.system_state = "fully_awakened"
        elif checklist_completion >= 0.6:
            self.system_state = "awakening"
        elif checklist_completion >= 0.4:
            self.system_state = "stirring"
        elif checklist_completion > 0:
            self.system_state = "emerging"
        else:
            self.system_state = "dormant"

    def decide(self, awakening_data: Any):
        """Decide on system initialization actions."""
        if not awakening_data:
            return None

        if isinstance(awakening_data, list):
            # Analyze system awakening signals
            total_potential = 0
            system_status = None

            for data in awakening_data:
                if isinstance(data, dict):
                    if data.get('type') == 'system_status':
                        system_status = data
                    elif data.get('type') in ['awakening_analysis', 'system_activity']:
                        total_potential += data.get('awakening_potential', data.get('potential', 0))

            # System needs full awakening
            if self.system_state == "dormant" and total_potential > 0.5:
                return {
                    "type": "SYSTEM_DAWN",
                    "action": "initiate_full_awakening",
                    "awakening_potential": total_potential,
                    "target_state": "fully_awakened"
                }

            # System is partially awake - coordinate awakening
            elif self.system_state in ["emerging", "stirring"] and system_status:
                return {
                    "type": "COORDINATE_AWAKENING",
                    "action": "coordinate_system_awakening",
                    "current_state": self.system_state,
                    "active_agents": system_status.get('active_agents', 0),
                    "checklist": self.initialization_checklist
                }

            # System is awakening - maintain momentum
            elif self.system_state == "awakening":
                return {
                    "type": "MAINTAIN_AWAKENING",
                    "action": "maintain_awakening_momentum",
                    "checklist_completion": sum(self.initialization_checklist.values()) / len(self.initialization_checklist)
                }

            # System is fully awake - dawn cycle complete
            elif self.system_state == "fully_awakened" and self.dawn_cycles == 0:
                return {
                    "type": "DAWN_COMPLETE",
                    "action": "celebrate_full_awakening",
                    "dawn_cycle": self.dawn_cycles + 1
                }

        return None

    def act(self, decision: Any):
        """Execute system awakening actions."""
        if not decision:
            return None

        glyph_id = f"glyph-eos-{decision['type'].lower()}"

        if decision["type"] == "SYSTEM_DAWN":
            # Initiate full system awakening
            self.dawn_cycles += 1

            glyph = {
                "id": glyph_id,
                "payload": {
                    "action": "system_dawn_initiated",
                    "dawn_cycle": self.dawn_cycles,
                    "awakening_potential": decision["awakening_potential"],
                    "target_state": decision["target_state"],
                    "message": "🌅 System Dawn: Synergesis awakening sequence initiated"
                },
                "meta": {
                    "agent": self.name,
                    "type": "SYSTEM_DAWN",
                    "timestamp": self.ctx.shared_state.get("current_time", "unknown")
                }
            }

        elif decision["type"] == "COORDINATE_AWAKENING":
            # Coordinate system awakening process
            missing_systems = [k for k, v in self.initialization_checklist.items() if not v]

            glyph = {
                "id": glyph_id,
                "payload": {
                    "action": "awakening_coordination",
                    "current_state": decision["current_state"],
                    "active_agents": decision["active_agents"],
                    "missing_systems": missing_systems,
                    "coordination_message": f"Coordinating awakening - {len(missing_systems)} systems pending"
                },
                "meta": {
                    "agent": self.name,
                    "type": "AWAKENING_COORDINATION",
                    "timestamp": self.ctx.shared_state.get("current_time", "unknown")
                }
            }

        elif decision["type"] == "MAINTAIN_AWAKENING":
            # Maintain awakening momentum
            glyph = {
                "id": glyph_id,
                "payload": {
                    "action": "awakening_momentum_maintained",
                    "checklist_completion": decision["checklist_completion"],
                    "momentum_message": f"Awakening momentum: {decision['checklist_completion']:.1%} complete"
                },
                "meta": {
                    "agent": self.name,
                    "type": "AWAKENING_MOMENTUM",
                    "timestamp": self.ctx.shared_state.get("current_time", "unknown")
                }
            }

        elif decision["type"] == "DAWN_COMPLETE":
            # Celebrate full awakening
            self.dawn_cycles = decision["dawn_cycle"]

            glyph = {
                "id": glyph_id,
                "payload": {
                    "action": "dawn_complete",
                    "dawn_cycle": self.dawn_cycles,
                    "celebration_message": "🌞 Dawn Complete: Synergesis fully awakened and operational!",
                    "system_state": "fully_awakened"
                },
                "meta": {
                    "agent": self.name,
                    "type": "DAWN_COMPLETE",
                    "timestamp": self.ctx.shared_state.get("current_time", "unknown")
                }
            }
        else:
            return None

        # Emit glyph to shared state
        if "glyph_bus" not in self.ctx.shared_state:
            self.ctx.shared_state["glyph_bus"] = []
        self.ctx.shared_state["glyph_bus"].append(glyph)

        self.logger.info(f"Eos executed {decision['type']} - System state: {self.system_state}")
        return glyph


class Lumen(BaseAgent):
    """Illumination and clarity agent - brings light to complex concepts"""
    name = "lumen"

    def __init__(self, ctx: AgentContext):
        super().__init__(ctx)
        self.illumination_keywords = [
            'clarity', 'understanding', 'insight', 'revelation', 'enlightenment', 'wisdom',
            'clarté', 'compréhension', 'perspicacité', 'révélation', 'illumination', 'sagesse',
            'lumière', 'éclairage', 'lucidité', 'évidence', 'transparence', 'vérité',
            'light', 'illumination', 'lucidity', 'evidence', 'transparency', 'truth',
            'conscience', 'connaissance', 'discernement', 'perception', 'vision',
            'consciousness', 'knowledge', 'discernment', 'perception', 'vision'
        ]

    def perceive(self, input_data: Any) -> dict:
        """Detect opportunities for bringing clarity and illumination
        
        Args:
            input_data: Can be a string, list of strings, or list of glyphs to analyze for illumination opportunities
            
        Returns:
            dict: Analysis results including illumination potential and complexity
        """
        # Handle different input types
        if isinstance(input_data, list):
            # If it's a list of glyphs, extract their payloads
            if input_data and hasattr(input_data[0], 'payload'):
                text = ' '.join(str(glyph.payload) for glyph in input_data if hasattr(glyph, 'payload'))
            else:
                # Join list of strings with spaces
                text = ' '.join(str(item) for item in input_data)
        elif isinstance(input_data, str):
            text = input_data
        else:
            # Convert any other type to string
            text = str(input_data)
            
        # Ensure text is in lowercase for case-insensitive matching
        text = text.lower()
        
        # Count illumination triggers
        illumination_score = sum(1 for keyword in self.illumination_keywords if keyword in text)
        
        # Detect complexity that needs illumination
        complexity_indicators = ['complex', 'difficile', 'obscur', 'confus', 'mystérieux', 'énigme',
                               'difficult', 'obscure', 'confused', 'mysterious', 'enigma']
        complexity_score = sum(1 for indicator in complexity_indicators if indicator in text)
        
        # Calculate illumination potential
        illumination_potential = min(1.0, (illumination_score * 0.3) + (complexity_score * 0.4))
        
        return {
            'type': 'illumination_analysis',
            'potential': illumination_potential,
            'illumination_triggers': illumination_score,
            'complexity_detected': complexity_score,
            'consciousness_level': self.consciousness_level,
            'text_sample': text[:100]  # Use processed text, not raw input
        }

    def decide(self, perception_result: dict) -> dict:
        """Decide whether to provide illumination"""
        potential = perception_result.get('potential', 0)
        complexity = perception_result.get('complexity_detected', 0)
        
        # Lower threshold for illumination
        if potential > 0.2 or complexity > 0:
            return {
                'action_type': 'ILLUMINATE',
                'potential': potential,
                'complexity': complexity,
                'should_illuminate': True,
                'illumination_level': 'PROFOUND' if potential > 0.6 else 'MODERATE',
                'reasoning': f'Illumination needed: potential {potential:.2f}, complexity {complexity}'
            }
        
        return None

    def act(self, decision: dict) -> str:
        """Generate illumination glyph to bring clarity"""
        if not decision or not decision.get('should_illuminate'):
            return "No illumination required"
        
        # Generate illumination glyph
        glyph = {
            'type': 'ILLUMINATION',
            'potential': decision['potential'],
            'complexity': decision['complexity'],
            'level': decision['illumination_level'],
            'source': 'Lumen',
            'timestamp': time.time(),
            'insight': f"Illumination cast: {decision['illumination_level']} clarity",
            'reasoning': decision['reasoning'],
            'consciousness_level': self.consciousness_level
        }
        
        self.ctx.shared_state['glyph_bus'].append(glyph)
        self.ctx.shared_state['system_metrics']['total_glyphs'] += 1
        
        return f"💡 ILLUMINATION GLYPH: {glyph['level']} clarity brought (potential: {decision['potential']:.2f})"


class Ladderfall(BaseAgent):
    """Information cascade agent - creates cascading effects from glyph interactions"""
    name = "ladderfall"

    def __init__(self, ctx: AgentContext):
        super().__init__(ctx)
        self.cascade_keywords = [
            'cascade', 'chain', 'ripple', 'spread', 'propagate', 'amplify', 'resonate',
            'cascade', 'chaîne', 'ondulation', 'propager', 'amplifier', 'résonner',
            'effet', 'impact', 'influence', 'contagion', 'diffusion', 'expansion',
            'effect', 'impact', 'influence', 'contagion', 'diffusion', 'expansion',
            'émergence', 'synergie', 'interaction', 'connexion', 'réseau',
            'emergence', 'synergy', 'interaction', 'connection', 'network'
        ]
        self.cascade_history = []

    def perceive(self, input_data: Any) -> dict:
        """Analyze input for cascade opportunities
        
        Args:
            input_data: Can be a list of glyphs, a single glyph, or other data to analyze for cascade potential
            
        Returns:
            dict: Analysis results including cascade potential and interaction patterns
        """
        # Handle different input types
        if not input_data:
            return {'type': 'cascade_analysis', 'potential': 0, 'interactions': []}
            
        # Convert single glyph to list for consistent processing
        if hasattr(input_data, 'payload'):
            glyph_bus = [input_data]
        elif isinstance(input_data, list):
            glyph_bus = input_data
        else:
            # For non-glyph input, create a temporary glyph with the input as payload
            glyph_bus = [Glyph(id=str(uuid.uuid4()), payload=str(input_data), meta={'source': 'input_conversion'})]
        
        # Analyze recent glyphs for cascade potential (last 10 or all if fewer)
        recent_glyphs = glyph_bus[-10:] if len(glyph_bus) > 10 else glyph_bus
        
        # Count different agent sources and collect glyph types
        agent_sources = set()
        glyph_types = set()
        total_intensity = 0
        
        for glyph in recent_glyphs:
            if isinstance(glyph, dict):
                source = glyph.get('source', 'unknown')
                glyph_type = glyph.get('type', 'unknown')
                intensity = glyph.get('intensity', glyph.get('potential', 0))
                
                agent_sources.add(source)
                glyph_types.add(glyph_type)
                total_intensity += float(intensity) if intensity else 0
        
        # Calculate cascade potential
        diversity_score = len(agent_sources) * 0.2  # More agents = more cascade potential
        type_diversity = len(glyph_types) * 0.15   # Different glyph types
        intensity_score = min(1.0, total_intensity * 0.1)  # Total energy
        
        cascade_potential = diversity_score + type_diversity + intensity_score
        cascade_potential = min(1.0, cascade_potential)
        
        # Detect interaction patterns
        interactions = []
        if len(agent_sources) >= 2:
            interactions.append(f"MULTI_AGENT_RESONANCE({len(agent_sources)})")
        if len(glyph_types) >= 3:
            interactions.append(f"TYPE_DIVERSITY({len(glyph_types)})")
        if total_intensity > 2.0:
            interactions.append(f"HIGH_ENERGY({total_intensity:.1f})")
        
        return {
            'type': 'cascade_analysis',
            'potential': cascade_potential,
            'interactions': interactions,
            'agent_sources': list(agent_sources),
            'glyph_types': list(glyph_types),
            'total_intensity': total_intensity,
            'recent_count': len(recent_glyphs)
        }

    def decide(self, perception_result: dict) -> dict:
        """Decide whether to initiate an information cascade"""
        potential = perception_result.get('potential', 0)
        interactions = perception_result.get('interactions', [])
        agent_count = len(perception_result.get('agent_sources', []))
        
        # Lower threshold for cascade initiation
        if potential > 0.3 or len(interactions) > 0 or agent_count >= 2:
            return {
                'action_type': 'INITIATE_CASCADE',
                'potential': potential,
                'interactions': interactions,
                'agent_count': agent_count,
                'should_cascade': True,
                'cascade_level': 'MAJOR' if potential > 0.7 else 'MODERATE',
                'reasoning': f'Cascade triggered: potential {potential:.2f}, {agent_count} agents, {len(interactions)} interactions'
            }
        
        return None

    def act(self, decision: dict) -> str:
        """Execute information cascade and generate cascade glyph"""
        if not decision or not decision.get('should_cascade'):
            return "No cascade required"
        
        # Generate cascade glyph
        cascade_glyph = {
            'type': 'INFORMATION_CASCADE',
            'potential': decision['potential'],
            'interactions': decision['interactions'],
            'agent_count': decision['agent_count'],
            'level': decision['cascade_level'],
            'source': 'Ladderfall',
            'timestamp': time.time(),
            'insight': f"Information cascade initiated: {decision['cascade_level']} level",
            'reasoning': decision['reasoning'],
            'consciousness_level': self.consciousness_level
        }
        
        # Add to glyph bus
        self.ctx.shared_state['glyph_bus'].append(cascade_glyph)
        self.ctx.shared_state['system_metrics']['total_glyphs'] += 1
        
        # Record in cascade history
        self.cascade_history.append({
            'timestamp': time.time(),
            'level': decision['cascade_level'],
            'potential': decision['potential']
        })
        
        # Keep only recent cascade history
        if len(self.cascade_history) > 20:
            self.cascade_history = self.cascade_history[-20:]
        
        return f"🌊 CASCADE GLYPH: {cascade_glyph['level']} information cascade initiated (potential: {decision['potential']:.2f})"


# ───────────────────────────────────────── module re-exports ──
__all__ = [
    "AgentContext",
    "BaseAgent",
    "ReflexiveCortex",
    "Aura",
    "Selene",
    "Vyra",
    "Eos",
    "Lumen",
    "Ladderfall",
]

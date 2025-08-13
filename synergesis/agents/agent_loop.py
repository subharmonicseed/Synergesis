# File: agent_loop.py
# Description: Synergesis Master Event Loop & Agent Orchestrator v3.0

import logging
import os
import schedule
import time
import datetime
from typing import Dict, Any
from synergesis.cognitive_core.intention_generator import IntentionGenerator
from synergesis.cognitive_core.simulation_engine import SimulationEngine
from synergesis.cognitive_core.memory_system import get_memory

# Import agent classes
from synergesis.agents.core_agents import (
    AgentContext, Aura, Selene, Vyra, Eos, Lumen, Ladderfall, ReflexiveCortex
)
from synergesis.agents.hrm_agent import HRMControllerAgent
from synergesis.agents.manus_bridge import get_reflexive_cortex_class
from synergesis.agents.nous import Nous
from synergesis.agents.thales import Thales
from synergesis.agents.deepresearch import DeepResearchAgent
# Import agents with fallback handling
try:
    from synergesis.agents.hermes import HermesAgent
except ImportError:
    HermesAgent = None
    
try:
    from synergesis.agents.chronos import ChronosAgent
except ImportError:
    ChronosAgent = None
    
try:
    from synergesis.agents.atlas import AtlasAgent
except ImportError:
    AtlasAgent = None
    
try:
    from synergesis.agents.morpheus import MorpheusAgent
except ImportError:
    MorpheusAgent = None
    
try:
    from synergesis.agents.apollo import ApolloAgent
except ImportError:
    ApolloAgent = None
    
try:
    from synergesis.agents.hestia import HestiaAgent
except ImportError:
    HestiaAgent = None
from synergesis.storage.neo4j_interface import Neo4jStorage

# Shared state for all agents
shared_state: dict = {
    "glyph_bus": [],
    "current_time": "unknown",
    "system_metrics": {
        "total_glyphs": 0,
        "active_agents": 0,
        "learning_events": 0,
        "creative_sparks": 0,
        "emotional_rebalances": 0,
        "contradictions_detected": 0,
        "cascades_initiated": 0,
        "wisdom_distilled": 0,
        "system_awakenings": 0
    }
}

# Agent context
ctx = AgentContext(config={}, shared_state=shared_state)

# Setup logging early (required before initializations that use logger)
logger = logging.getLogger("SynergesisAgentLoop")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)

# Initialize Neo4j connector for Manus cortex
neo4j_connector = Neo4jStorage(
    uri=os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
    user=os.getenv('NEO4J_USER', 'neo4j'),
    password=os.getenv('NEO4J_PASSWORD', 'password'),
    database=os.getenv('NEO4J_DATABASE', 'neo4j'),
    encrypted=os.getenv('NEO4J_ENCRYPTED', 'false').lower() == 'true'
)

# Initialize Reflexive Cortex
ReflexiveCortex = get_reflexive_cortex_class()
logger.info("Instantiating Manus Reflexive Cortex with Neo4jStorage connector")
reflexive_cortex = ReflexiveCortex(neo4j_connector=neo4j_connector)  # type: ignore[arg-type]

# Initialize core agents
nous_agent = Nous(ctx)
thales_agent = Thales(ctx)
aura_agent = Aura(ctx)
selene_agent = Selene(ctx)
vyra_agent = Vyra(ctx)
eos_agent = Eos(ctx)
lumen_agent = Lumen(ctx)
ladderfall_agent = Ladderfall(ctx)
deepresearch_agent = DeepResearchAgent(ctx)

# Initialize new agents with proper variable references
chronos_agent = ChronosAgent(nous_agent) if ChronosAgent else None
# Allowed domains for Hermes web fetch
HERMES_ALLOW_LIST = {"arxiv.org", "docs.python.org"}
hermes_agent = HermesAgent(nous_agent) if HermesAgent else None
atlas_agent = AtlasAgent(nous_agent) if AtlasAgent else None
morpheus_agent = MorpheusAgent(nous_agent) if MorpheusAgent else None
apollo_agent = ApolloAgent(nous_agent) if ApolloAgent else None
hestia_agent = HestiaAgent(nous_agent) if HestiaAgent else None

# Update current time helper
def update_current_time():
    import datetime
    shared_state["current_time"] = datetime.datetime.now().isoformat()

# Agent task functions
def task_translate_batch():
    print("[agent_loop] Running: Translate batch")

def task_echo_check():
    print("[agent_loop] Running: Echo check")

def task_llm_prompt():
    print("[agent_loop] Running: LLM prompt cycle")

def task_observe():
    print("[agent_loop] Running: Observer mode")

def task_ingest_check():
    print("[agent_loop] Running: Ingest check")

def task_coherence_check():
    # Run Reflexive Cortex over current glyph bus
    glyph_bus = shared_state.get("glyph_bus", [])
    # Flexibly invoke the Manus Reflexive Cortex depending on implementation
    if callable(reflexive_cortex):
        reflexive_cortex(glyph_bus)  # stub implementation defines __call__
    elif hasattr(reflexive_cortex, "reflect"):
        reflexive_cortex.reflect({"glyph_bus": glyph_bus})
    elif hasattr(reflexive_cortex, "generate_observations"):
        observations = reflexive_cortex.generate_observations()
        logger.info("Reflexive cortex observations: %s", observations)
    else:
        logger.warning("Reflexive cortex implementation has no callable entry point")

def task_nous_cycle():
    # Let NOUS process any incoming glyphs/events
    nous_agent()

def task_thales_analysis():
    """Thales contradiction detection cycle."""
    update_current_time()
    print("[agent_loop] Running: Thales analysis")
    
    # Get current glyph bus for analysis
    glyph_bus = shared_state.get("glyph_bus", [])
    
    # Run Thales analysis cycle
    perceived_data = thales_agent.perceive(glyph_bus)
    decision = thales_agent.decide(perceived_data)
    result = thales_agent.act(decision)
    
    if result:
        # Ensure result is a dict
        if isinstance(result, str):
            result = {"content": result, "type": "contradiction"}
        
        # Create glyph structure
        glyph = {
            "id": f"thales_{int(time.time())}",
            "agent": "Thales",
            "type": "contradiction",
            "content": result,
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "perceived_data": perceived_data,
                "decision": decision
            }
        }
        
        # Save to Neo4j
        if persist_glyph_to_neo4j(glyph):
            glyph_bus.append(glyph)
            shared_state["glyph_bus"] = glyph_bus[-100:]
            shared_state["system_metrics"]["contradictions_detected"] += 1
            print(f"[agent_loop] Thales contradiction glyph persisted: {glyph['id']}")
        else:
            print("[agent_loop] Thales: failed to persist contradiction glyph")
    else:
        print("[agent_loop] Thales: no contradictions detected")

def task_aura_resonance():
    """Aura emotional resonance cycle."""
    update_current_time()
    print("[agent_loop] Running: Aura emotional resonance")
    
    try:
        glyph_bus = shared_state.get("glyph_bus", [])
        perceived_data = aura_agent.perceive(glyph_bus)
        decision = aura_agent.decide(perceived_data)
        result = aura_agent.act(decision)
        
        if result and isinstance(result, dict):
            glyph = result.get('glyph', result)
            if isinstance(glyph, dict):
                glyph['agent'] = 'Aura'
                glyph['timestamp'] = datetime.now().isoformat()
                
                # Save to Neo4j
                if persist_glyph_to_neo4j(glyph):
                    # Add to bus
                    glyph_bus.append(glyph)
                    shared_state["glyph_bus"] = glyph_bus[-100:]
                    shared_state["system_metrics"]["emotional_rebalances"] += 1
                    
                    action = glyph.get('payload', {}).get('action', 'unknown')
                    print(f"[agent_loop] Aura emitted emotional glyph: {action}")
                else:
                    print(f"[agent_loop] Aura: failed to persist glyph")
            else:
                print(f"[agent_loop] Aura result: {result}")
        else:
            print("[agent_loop] Aura: no action taken")
            
    except Exception as e:
        print(f"[agent_loop] Error in Aura resonance cycle: {str(e)}")
        import traceback
        traceback.print_exc()

def task_selene_creativity():
    """Selene creativity spark cycle."""
    try:
        update_current_time()
        print("[agent_loop] Running: Selene creativity")
        
        glyph_bus = shared_state.get("glyph_bus", [])
        
        # Ensure we have valid input for Selene
        if not glyph_bus or not isinstance(glyph_bus, list):
            print("[agent_loop] No glyphs to process")
            return
            
        # Process the glyph bus
        try:
            perceived_data = selene_agent.perceive(glyph_bus)
            if not perceived_data:
                print("[agent_loop] No perception data from Selene")
                return
                
            decision = selene_agent.decide(perceived_data)
            if not decision:
                print("[agent_loop] No decision from Selene")
                return
                
            result = selene_agent.act(decision)
            
            if result:
                shared_state["system_metrics"]["creative_sparks"] += 1
                # Handle both dict and string results gracefully
                if isinstance(result, dict):
                    action = result.get('payload', {}).get('action', 'unknown')
                    print(f"[agent_loop] Selene sparked creativity: {action}")
                else:
                    print(f"[agent_loop] Selene sparked creativity: {result}")
                
        except Exception as e:
            print(f"[agent_loop] Error in Selene creativity cycle: {str(e)}")
            
    except Exception as e:
        print(f"[agent_loop] Critical error in task_selene_creativity: {str(e)}")

def task_hermes_cycle():
    """Hermes web-fetch cycle with allow-list filtering."""
    if not hermes_agent:
        return
    # Look for glyphs requesting external info, e.g. {type:"query", content:"fetch:https://arxiv.org/abs/1234"}
    requests_to_process = []
    for g in shared_state.get("glyph_bus", [])[-20:]:  # recent glyphs
        if g.get("type") == "query" and g["content"].startswith("fetch:") and not g.get("processed_by_hermes"):
            requests_to_process.append(g)

    import re, requests, time as _t
    for req in requests_to_process:
        url = req["content"].split("fetch:",1)[1].strip()
        domain = re.sub(r"^https?://", "", url).split("/",1)[0]
        if domain not in HERMES_ALLOW_LIST:
            glyph = {"type":"response","content":f"Hermes: domain {domain} not allowed","timestamp":_t.time()}
            shared_state["glyph_bus"].append(glyph)
            req["processed_by_hermes"] = True
            continue
        try:
            r = requests.get(url, timeout=10)
            text = r.text[:5000]  # limit size
            glyph = {
                "type": "web_content",
                "source": url,
                "content": text,
                "timestamp": _t.time()
            }
            shared_state["glyph_bus"].append(glyph)
            reply = {"type":"response","content":f"Hermes fetched {url} (len={len(text)})","timestamp":_t.time()}
            shared_state["glyph_bus"].append(reply)
        except Exception as e:
            shared_state["glyph_bus"].append({"type":"response","content":f"Hermes error fetching {url}: {e}","timestamp":_t.time()})
        req["processed_by_hermes"] = True


def task_vyra_learning():
    """Vyra adaptive learning cycle."""
    update_current_time()
    print("[agent_loop] Running: Vyra adaptive learning")
    
    try:
        # Initialize storage reference
        storage = shared_state.get("storage")
        glyph_bus = shared_state.get("glyph_bus", [])
        
        # Get perception and make decision
        perceived_data = vyra_agent.perceive(glyph_bus)
        decision = vyra_agent.decide(perceived_data)
        result = vyra_agent.act(decision)
        
        if not result:
            print("[agent_loop] Vyra: No result from act()")
            return
            
        # Update metrics
        shared_state["system_metrics"]["learning_events"] += 1
        
        # Handle different result types safely
        if isinstance(result, dict):
            action = result.get('payload', {}).get('action', 'unknown')
            print(f"[agent_loop] Vyra learned: {action}")
            # If there's a glyph, it will be handled by the storage logic below
        else:
            # Handle non-dictionary result (e.g., a simple string)
            print(f"[agent_loop] Vyra returned raw result: {str(result)}")

        # Unified Glyph Handling and Persistence
        glyph_to_save = None
        if isinstance(result, dict) and 'glyph' in result:
            glyph_to_save = result['glyph']
        elif isinstance(result, str):
            glyph_to_save = {'type': 'vyra_learning', 'content': result}

        if glyph_to_save and storage:
            if not isinstance(glyph_to_save, dict):
                glyph_to_save = {'content': str(glyph_to_save), 'type': 'vyra_learning_error'}
            
            # Ensure timestamp exists
            if 'timestamp' not in glyph_to_save:
                glyph_to_save['timestamp'] = shared_state.get("current_time")
            
            try:
                storage.save_glyph(glyph_to_save)
                print(f"[agent_loop] Saved Vyra glyph to Neo4j: {glyph_to_save.get('id', glyph_to_save.get('content'))}")
                # Add to the bus only after successful save
                glyph_bus.append(glyph_to_save)
                shared_state["glyph_bus"] = glyph_bus[-100:]
            except Exception as e:
                print(f"[agent_loop] Error saving Vyra glyph: {str(e)}")
    except Exception as e:
        print(f"[agent_loop] Error in Vyra learning cycle: {str(e)}")
        import traceback
        traceback.print_exc()

def task_eos_awakening():
    """Eos system awakening coordination cycle."""
    update_current_time()
    print("[agent_loop] Running: Eos system awakening")
    
    glyph_bus = shared_state.get("glyph_bus", [])
    perceived_data = eos_agent.perceive(glyph_bus)
    decision = eos_agent.decide(perceived_data)
    result = eos_agent.act(decision)
    
    if result:
        shared_state["system_metrics"]["system_awakenings"] += 1
        # Handle both dict and string results gracefully
        if isinstance(result, dict):
            action = result.get('payload', {}).get('action', 'unknown')
            print(f"[agent_loop] Eos coordinated awakening: {action}")
        else:
            print(f"[agent_loop] Eos coordinated awakening: {result}")

def task_lumen_synthesis():
    """Lumen wisdom synthesis cycle."""
    update_current_time()
    print("[agent_loop] Running: Lumen wisdom synthesis")
    
    glyph_bus = shared_state.get("glyph_bus", [])
    perceived_data = lumen_agent.perceive(glyph_bus)
    decision = lumen_agent.decide(perceived_data)
    result = lumen_agent.act(decision)
    
    if result:
        shared_state["system_metrics"]["wisdom_distilled"] += 1
        action = result.get('payload', {}).get('action', 'unknown') if isinstance(result, dict) else str(result)
        print(f"[agent_loop] Lumen synthesized wisdom: {action}")
{{ ... }}
    perceived_data = ladderfall_agent.perceive(glyph_bus)
    decision = ladderfall_agent.decide(perceived_data)
    result = ladderfall_agent.act(decision)
    
    if result:
        shared_state["system_metrics"]["cascades_initiated"] += 1
        if isinstance(result, dict):
            action = result.get('payload', {}).get('action', 'unknown') if isinstance(result, dict) else str(result)
            print(f"[agent_loop] Ladderfall cascaded: {action}")
        else:
            print(f"[agent_loop] Ladderfall returned raw string: {result}")

def task_deepresearch_cycle():
    """DeepResearch external knowledge acquisition cycle."""
    update_current_time()
    print("[agent_loop] Running: DeepResearch knowledge acquisition")
    
    # Rotate through research domains for variety
    research_topics = [
        "artificial intelligence optimization",
        "quantum computing advances", 
        "collective intelligence emergence",
        "consciousness research",
        "biomimetic systems"
    ]
    
    import random
    topic = random.choice(research_topics)
    
    try:
        result = deepresearch_agent(topic)
        shared_state["system_metrics"]["learning_events"] += 1
        print(f"[agent_loop] DeepResearch completed: {topic}")
    except Exception as e:
        print(f"[agent_loop] DeepResearch error: {e}")

def task_generate_and_simulate():
    mem = get_memory()
    print(f"[agent_loop] Running: Generate and simulate (memory size: {len(mem)})")

def persist_glyph_to_neo4j(glyph: Dict[str, Any]) -> bool:
    """Persist a single glyph to Neo4j storage."""
    try:
        storage = shared_state.get('storage')
        if storage and hasattr(storage, 'save_glyph'):
            storage.save_glyph(glyph)
            logger.debug(f"✅ Glyph persisted: {glyph.get('id', glyph.get('type', 'unknown'))}")
            return True
        else:
            logger.warning("❌ No storage available for glyph persistence")
            return False
    except Exception as e:
        logger.error(f"❌ Error persisting glyph: {e}")
        return False

def process_glyph_bus_persistence():
    """Process all glyphs in the bus and persist them to Neo4j."""
    try:
        glyph_bus = shared_state.get("glyph_bus", [])
        storage = shared_state.get('storage')
        
        if not storage:
            logger.warning("❌ No storage available for glyph persistence")
            return
        
        persisted_count = 0
        for glyph in glyph_bus:
            if isinstance(glyph, dict) and 'id' in glyph:
                if persist_glyph_to_neo4j(glyph):
                    persisted_count += 1
        
        if persisted_count > 0:
            logger.info(f"📊 Persisted {persisted_count} glyphs to Neo4j")
            
    except Exception as e:
        logger.error(f"❌ Error processing glyph bus persistence: {e}")

def task_system_metrics():
    """Display system metrics and process glyph persistence."""
    update_current_time()
    glyph_count = len(shared_state.get("glyph_bus", []))
    metrics = shared_state.get("system_metrics", {})
    
    # Process glyph persistence
    process_glyph_bus_persistence()
    
    print(f"\n🌟 SYNERGESIS SYSTEM METRICS 🌟")
    print(f"Active Glyphs: {glyph_count}")
    print(f"Contradictions Detected: {metrics.get('contradictions_detected', 0)}")
    print(f"Creative Sparks: {metrics.get('creative_sparks', 0)}")
    print(f"Emotional Rebalances: {metrics.get('emotional_rebalances', 0)}")
    print(f"Learning Events: {metrics.get('learning_events', 0)}")
    print(f"System Awakenings: {metrics.get('system_awakenings', 0)}")
    print(f"Wisdom Distilled: {metrics.get('wisdom_distilled', 0)}")
    print(f"Cascades Initiated: {metrics.get('cascades_initiated', 0)}")
    print(f"Current Time: {shared_state.get('current_time', 'unknown')}")
    print("=" * 50)
    
    # Update active agents count
    shared_state["system_metrics"]["active_agents"] = 14  # Updated for 14 agents
    shared_state["system_metrics"]["total_glyphs"] = glyph_count

def get_memory():
    return shared_state.get("glyph_bus", [])

# Setup logging
logger = logging.getLogger("SynergesisAgentLoop")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)
    
# Initialize all agents
from synergesis.storage.neo4j_interface import Neo4jStorage  # new import for Manus cortex

def setup_chronos_tasks():
    """Chronos-based scheduling is currently disabled."""
    logger.warning("Chronos scheduling is currently disabled")
    return False

def setup_basic_schedule():
    """Set up basic scheduling including HRM controller"""
    logger.info("Setting up basic scheduling with HRM controller")
    
    # Core agent tasks
    schedule.every(5).minutes.do(task_aura_resonance)
    schedule.every(10).minutes.do(task_hermes_cycle)
    schedule.every(8).minutes.do(task_selene_creativity)
    schedule.every(10).minutes.do(task_thales_analysis)
    schedule.every(15).minutes.do(task_deepresearch_analysis)
    schedule.every(5).minutes.do(task_chronos_health_check)
    schedule.every(12).minutes.do(task_lumen_synthesis)
    schedule.every(8).minutes.do(task_ladderfall_flow)
    schedule.every(15).minutes.do(task_eos_coordination)
    
    # HRM controller runs every 7 minutes to orchestrate
    schedule.every(7).minutes.do(task_hrm_controller)
    
    # System metrics
    schedule.every(2).minutes.do(task_system_metrics)
    """Set up basic scheduling using the schedule library, including Hermes."""
    """Set up basic scheduling using the schedule library."""
    logger.info("Setting up basic scheduling with frequent intervals for testing")
    
    # Core agent tasks with shorter intervals for testing
    schedule.every(5).minutes.do(task_aura_resonance)
    # Hermes every 6 minutes
    schedule.every(10).minutes.do(task_hermes_cycle)
    schedule.every(8).minutes.do(task_selene_creativity)
    schedule.every(10).minutes.do(task_thales_analysis)
    schedule.every(15).minutes.do(task_deepresearch_analysis)
    schedule.every(5).minutes.do(task_chronos_health_check)
    schedule.every(7).minutes.do(task_hermes_execution)
    schedule.every(12).minutes.do(task_atlas_visualization)
    schedule.every(30).minutes.do(task_morpheus_simulation)
    schedule.every(20).minutes.do(task_apollo_generation)
    schedule.every(60).minutes.do(task_hestia_sync)
    schedule.every(30).seconds.do(task_vyra_learning)
    schedule.every(60).seconds.do(task_eos_awakening)
    schedule.every(180).seconds.do(task_lumen_synthesis)
    schedule.every(300).seconds.do(task_ladderfall_cascade)
    schedule.every(600).seconds.do(task_deepresearch_cycle)
    
    # System monitoring
    schedule.every(30).seconds.do(task_system_metrics)
    
    logger.info("Basic scheduling setup complete")

def setup_schedule():
    """Set up the scheduling system, using Chronos if available."""
    logger.info("🌅 Setting up Synergesis Agent Loop...")
    
    # Try to set up Chronos scheduling, fall back to basic if not available
    if not setup_chronos_tasks():
        setup_basic_schedule()

def execute_task(task_name: str, agent_name: str):
    """Execute a task by name with error handling."""
    try:
        task_func = globals().get(task_name)
        if task_func and callable(task_func):
            logger.debug(f"Executing task: {task_name} for agent: {agent_name}")
            return task_func()
        else:
            logger.warning(f"Task function {task_name} not found or not callable")
    except Exception as e:
        logger.error(f"Error executing task {task_name}: {e}")
    return None

def process_chronos_events():
    """Process any pending Chronos events if available."""
    if hasattr(chronos_agent, 'initialized') and chronos_agent.initialized:
        try:
            # Let Chronos process its internal events
            chronos_agent()
            
            # Check for any system health alerts
            health_status = chronos_agent.ctx.shared_state.get('system_health', {})
            if health_status.get('status') == 'WARNING':
                logger.warning(f"System health warning: {health_status.get('message')}")
            elif health_status.get('status') == 'CRITICAL':
                logger.critical(f"CRITICAL SYSTEM HEALTH: {health_status.get('message')}")
                # Potentially trigger emergency protocols here
                
        except Exception as e:
            logger.error(f"Error processing Chronos events: {e}")

def main_loop():
    """Run the main agent loop with the configured schedule."""
    logger.info("🌟 Starting Synergesis Collective Intelligence System...")
    logger.info("🧠 Core Agents: Thales, Nous, Aura, Selene, Vyra, Eos, Lumen, Ladderfall, Hermes, Chronos, Atlas, Morpheus, Apollo, Hestia")

    # Neo4jStorage and ReflexiveCortex are initialized globally. We just need to
    # ensure they are correctly placed in the shared_state for the agents.
    shared_state['storage'] = neo4j_connector
    shared_state['reflexive_cortex'] = reflexive_cortex
    logger.info("💾 Neo4j storage and Manus Cortex are configured for the main loop.")
    
    # Initialize the scheduling system
    setup_schedule()
    
    # Initialize shared state with agent references
    agents = {
        "Aura": Aura(ctx),
        "Selene": Selene(ctx),
        "Vyra": Vyra(ctx),
        "Eos": Eos(ctx),
        "Lumen": Lumen(ctx),
        "Ladderfall": Ladderfall(ctx),
        "ReflexiveCortex": cortex,
        "Thales": Thales(nous),
        "DeepResearch": DeepResearchAgent(ctx),
        "Hermes": HermesAgent(nous),
        "Chronos": chronos_agent,
        "Atlas": AtlasAgent(nous),
        "Morpheus": MorpheusAgent(nous),
        "Apollo": ApolloAgent(nous),
        "Hestia": HestiaAgent(nous)
    }
    shared_state['agents'] = agents
    
    # Initial system check
    task_system_metrics()
    
    try:
        logger.info("🚀 Entering main execution loop...")
        while True:
            # Process scheduled tasks (basic scheduler)
            schedule.run_pending()
            
            # Process Chronos events if available
            process_chronos_events()
            
            # Small sleep to prevent CPU overutilization
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down Synergesis system...")
    except Exception as e:
        logger.error(f"❌ Unexpected error in main loop: {e}")
    finally:
        # Cleanup resources
        if hasattr(chronos_agent, 'initialized') and chronos_agent.initialized:
            try:
                chronos_agent.chronos.stop()
                logger.info("Chronos scheduler stopped")
            except Exception as e:
                logger.error(f"Error stopping Chronos: {e}")
        
        logger.info("✅ System shutdown complete")

def task_hrm_controller():
    """HRM meta-controller decides agent sequences"""
    try:
        from synergesis.agents.hrm_agent import HRMControllerAgent
        
        # Build agent registry
        agent_registry = {
            "thales": thales_agent,
            "vyra": vyra_agent,
            "selene": selene_agent,
            "lumen": lumen_agent,
            "aura": aura_agent,
            "ladderfall": ladderfall_agent,
            "eos": eos_agent,
            "deepresearch": deepresearch_agent
        }
        
        # Create HRM controller
        hrm = HRMControllerAgent(agent_registry, shared_state.get("glyph_bus", []))
        
        # Decide sequence
        current_glyphs = shared_state.get("glyph_bus", [])[-20:]
        sequence = hrm.decide_agent_sequence(current_glyphs)
        
        if sequence:
            logger.info(f"HRM executing sequence: {sequence}")
            results = hrm.execute_sequence(sequence)
            
            # Log results as glyphs
            glyph = {
                "type": "hrm_sequence",
                "content": json.dumps(results),
                "timestamp": time.time()
            }
            shared_state["glyph_bus"].append(glyph)
            
    except Exception as e:
        logger.error(f"HRM controller error: {e}")


if __name__ == "__main__":
    main_loop()

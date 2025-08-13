"""
Chronos Agent Integration for Synergesis

This module provides integration of the Chronos agent from the Manus pipeline
into the main Synergesis agent loop.
"""
import logging
from typing import Dict, Any
from synergesis.agents.agent_loop import AgentContext
from synergesis.storage.neo4j_interface import Neo4jStorage

# Import Chronos from Manus pipeline
try:
    from synergesis_pipeline.src.chronos import Chronos
    CHRONOS_AVAILABLE = True
except ImportError:
    CHRONOS_AVAILABLE = False
    logging.warning("Chronos agent not available. Falling back to basic scheduling.")

class ChronosAgent:
    """Wrapper for Chronos agent integration."""
    
    def __init__(self, ctx: AgentContext):
        """Initialize the Chronos agent."""
        self.ctx = ctx
        self.chronos = None
        self.initialized = False
        
        if CHRONOS_AVAILABLE:
            try:
                # Initialize Neo4j connector
                neo4j_connector = Neo4jStorage()
                
                # Initialize Chronos with configuration from shared state
                chronos_config = self.ctx.shared_state.get('chronos_config', {
                    'nous_api_url': 'http://localhost:8001',
                    'api_token': 'synergesis_nous_token_2025',
                    'db_path': '/data/chronos.db'
                })
                
                self.chronos = Chronos(
                    nous_api_url=chronos_config['nous_api_url'],
                    api_token=chronos_config['api_token'],
                    db_path=chronos_config['db_path']
                )
                
                # Start Chronos scheduler
                self.chronos.start()
                self.initialized = True
                logging.info("Chronos agent initialized and scheduler started")
                
            except Exception as e:
                logging.error(f"Failed to initialize Chronos agent: {e}")
                self.initialized = False
    
    def __call__(self):
        """Execute the Chronos agent cycle."""
        if not self.initialized or not self.chronos:
            return
            
        try:
            # Collect system metrics and update Chronos
            system_metrics = self._collect_system_metrics()
            self.chronos.time_series_analyzer.add_metrics(system_metrics)
            
            # Generate health report
            health_report = self.chronos._generate_health_report()
            
            # Log important system events
            if health_report.overall_status != "HEALTHY":
                logging.warning(f"System health alert: {health_report.overall_status}")
                for anomaly in health_report.anomalies:
                    logging.warning(f"Anomaly detected: {anomaly}")
            
            return health_report
            
        except Exception as e:
            logging.error(f"Error in Chronos agent cycle: {e}")
    
    def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect system metrics for Chronos analysis."""
        metrics = {
            'timestamp': time.time(),
            'total_concepts': len(self.ctx.shared_state.get('glyph_bus', [])),
            'knowledge_gaps': 0,  # Will be updated by Selene
            'logical_inconsistencies': 0,  # Will be updated by Thales
            'pending_suggestions': 0,  # Will be updated by Vyra
            'applied_suggestions': 0,  # Will be updated by Vyra
            'average_resonance': 0.0,  # Will be updated by Aura
            'average_weight': 0.0,  # Will be updated by Lumen
            'concept_types_distribution': {}  # Will be updated by Eos
        }
        
        # Update metrics from shared state if available
        metrics.update(self.ctx.shared_state.get('system_metrics', {}))
        return metrics
    
    def schedule_task(self, task_name: str, interval_seconds: int, target_agent: str, 
                     target_method: str, **params):
        """Schedule a new task with Chronos."""
        if not self.initialized or not self.chronos:
            return False
            
        try:
            task = {
                'name': task_name,
                'trigger_type': 'interval',
                'interval_seconds': interval_seconds,
                'target_agent': target_agent,
                'target_method': target_method,
                'parameters': params
            }
            
            self.chronos.schedule_task(task)
            return True
            
        except Exception as e:
            logging.error(f"Failed to schedule task {task_name}: {e}")
            return False

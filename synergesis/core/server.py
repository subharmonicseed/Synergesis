"""Synergesis DeepSeek Pro server entrypoint.
Run with:
    uvicorn synergesis.core.server:app --reload
"""
import threading
import logging
from synergesis.core.deepseek_pro import SynergesisCoreDeepSeekPro, SynergesisAPI
from synergesis.agents.main_loop_runner import run_agent_loop

# Initialize core components
_core = SynergesisCoreDeepSeekPro()
_api = SynergesisAPI(_core)
app = _api.app

# Configure logging
logger = logging.getLogger("SynergesisServer")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)

# Start agent loop in a separate thread
try:
    logger.info("Starting Synergesis agent loop in background thread...")
    agent_thread = threading.Thread(target=run_agent_loop, daemon=True)
    agent_thread.start()
    logger.info("Agent loop started successfully")
except Exception as e:
    logger.error(f"Failed to start agent loop: {e}", exc_info=True)

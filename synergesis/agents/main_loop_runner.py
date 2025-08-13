# File: main_loop_runner.py
# Description: Runner for the Synergesis agent loop to avoid circular imports

import time
import logging
import schedule
from synergesis.agents.agent_loop import setup_schedule

def run_agent_loop():
    """Run the main agent loop with the configured schedule."""
    logger = logging.getLogger("SynergesisAgentLoop")
    
    # Setup the schedule
    setup_schedule()
    
    logger.info("Starting Synergesis Agent Loop")
    
    try:
        # Main loop
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down Synergesis Agent Loop")
    except Exception as e:
        logger.error(f"Error in agent loop: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    run_agent_loop()

#!/usr/bin/env python3
"""
Archon Autonomous Agent Runner
=============================
Main entry point for running autonomous agents within Archon.
This replaces the old Synergesis agent loop with a native Archon implementation.
"""

import asyncio
import logging
import signal
import sys

# Import Archon services
from src.services.autonomous_agent_service import AutonomousAgentService
from src.services.neo4j_service import Neo4jService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('autonomous_agent.log')
    ]
)

logger = logging.getLogger("ArchonAutonomousRunner")

class AutonomousAgentRunner:
    """Main runner for autonomous agent system."""

    def __init__(self):
        self.running = False
        self.agent_service = None
        self.neo4j_service = None

    async def start(self):
        """Start the autonomous agent system."""
        logger.info("🌟 Starting Archon Autonomous Agent System...")
        logger.info("🧠 Agents: Vyra (Learning), Eos (Awakening), Thales (Analysis)")
        logger.info("🤖 Model: Mistral-7B-Instruct-v0.3 @ localhost:8080")

        try:
            # Initialize services
            self.neo4j_service = Neo4jService()
            self.agent_service = AutonomousAgentService()

            # Asynchronously initialize the agent service before starting
            await self.agent_service.initialize()

            # Start autonomous operation
            await self.agent_service.start_autonomous_operation()

        except Exception as e:
            logger.error(f"❌ Failed to start autonomous system: {e}")
            raise

    async def stop(self):
        """Stop the autonomous agent system."""
        logger.info("🛑 Stopping Archon Autonomous Agent System...")

        if self.agent_service:
            await self.agent_service.stop_autonomous_operation()

        if self.neo4j_service:
            await self.neo4j_service.close()

        logger.info("✅ Archon Autonomous Agent System stopped")

    def handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"📡 Received signal {signum}, shutting down...")
        asyncio.create_task(self.stop())

async def main():
    """Main entry point."""
    runner = AutonomousAgentRunner()

    # Setup signal handlers
    signal.signal(signal.SIGINT, runner.handle_signal)
    signal.signal(signal.SIGTERM, runner.handle_signal)

    try:
        await runner.start()
    except KeyboardInterrupt:
        logger.info("🛑 Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)
    finally:
        await runner.stop()

if __name__ == "__main__":
    logger.info("🚀 Starting Archon Autonomous Agent Runner...")
    asyncio.run(main())

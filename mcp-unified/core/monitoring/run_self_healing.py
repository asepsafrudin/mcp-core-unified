import asyncio
import logging
import os

from core.monitoring.self_healing_agent import SelfHealingAgent

logging.basicConfig(level=logging.INFO)


async def main():
    if os.getenv("SELF_HEALING_ENABLED", "true").lower() != "true":
        logging.info("Self-healing disabled via config")
        return

    agent = SelfHealingAgent()
    await agent.run_daily()


if __name__ == "__main__":
    asyncio.run(main())
"""
KDM Ventures LLC - AI Executive Bots
Three Telegram bots powered by Claude AI:
  - CFO Bot: Bookkeeping, taxes, budgeting, P&L
  - CMO Bot: Marketing campaigns, flyers, copywriting
  - COO Bot: Company operations, LLC management
"""

import asyncio
import logging
import os
from dotenv import load_dotenv
from bots.cfo_bot import CFOBot
from bots.cmo_bot import CMOBot
from bots.coo_bot import COOBot

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting KDM Ventures AI Executive Bots...")

    cfo = CFOBot()
    cmo = CMOBot()
    coo = COOBot()

    cfo_app = cfo.build_app()
    cmo_app = cmo.build_app()
    coo_app = coo.build_app()

    async with cfo_app, cmo_app, coo_app:
        await cfo_app.updater.start_polling(allowed_updates=["message"])
        await cmo_app.updater.start_polling(allowed_updates=["message"])
        await coo_app.updater.start_polling(allowed_updates=["message"])

        logger.info("✅ All 3 bots are running and polling for messages...")
        await asyncio.Event().wait()  # Run forever


if __name__ == "__main__":
    asyncio.run(main())

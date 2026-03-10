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
from bots.cfo_bot import CFOBot
from bots.cmo_bot import CMOBot
from bots.coo_bot import COOBot

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def main():
    cfo = CFOBot()
    cmo = CMOBot()
    coo = COOBot()

    logger.info("Starting KDM Ventures AI Executive Bots...")

    await asyncio.gather(
        cfo.run(),
        cmo.run(),
        coo.run(),
    )


if __name__ == "__main__":
    asyncio.run(main())

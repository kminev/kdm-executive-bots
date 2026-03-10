"""
KDM Ventures LLC - AI Executive Bots
Three Telegram bots powered by Claude AI:
  - CFO Bot: Bookkeeping, taxes, budgeting, P&L
  - CMO Bot: Marketing campaigns, flyers, copywriting
  - COO Bot: Company operations, LLC management

Uses the official python-telegram-bot v21 recommended pattern for
running multiple bots in one process on a shared event loop.
Reference: https://docs.python-telegram-bot.org/en/stable/telegram.ext.application.html
"""

import asyncio
import logging
import signal

from bots.cfo_bot import CFOBot
from bots.cmo_bot import CMOBot
from bots.coo_bot import COOBot

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting KDM Ventures AI Executive Bots...")

    # Build all three applications with handlers registered
    cfo_app = CFOBot().build_app()
    cmo_app = CMOBot().build_app()
    coo_app = COOBot().build_app()

    # Use async context managers — this handles initialize() and shutdown() cleanly
    async with cfo_app, cmo_app, coo_app:

        # Start all three apps
        await cfo_app.start()
        await cmo_app.start()
        await coo_app.start()

        # Start polling for all three concurrently on the SAME event loop
        # This is the key difference from run_polling() which tries to own the loop
        await asyncio.gather(
            cfo_app.updater.start_polling(drop_pending_updates=True),
            cmo_app.updater.start_polling(drop_pending_updates=True),
            coo_app.updater.start_polling(drop_pending_updates=True),
        )

        logger.info("✅ All 3 bots are running and polling for messages...")

        # Keep running until SIGINT or SIGTERM (Docker stop, Ctrl+C)
        stop_event = asyncio.Event()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        await stop_event.wait()

        logger.info("Shutdown signal received — stopping bots gracefully...")

        # Stop polling and apps in reverse order
        await asyncio.gather(
            cfo_app.updater.stop(),
            cmo_app.updater.stop(),
            coo_app.updater.stop(),
        )
        await asyncio.gather(
            cfo_app.stop(),
            cmo_app.stop(),
            coo_app.stop(),
        )

    logger.info("All bots shut down cleanly.")


if __name__ == "__main__":
    asyncio.run(main())

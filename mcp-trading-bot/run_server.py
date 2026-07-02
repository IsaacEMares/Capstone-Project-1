#!/usr/bin/env python3
"""Start the bot server (webhook receiver + control + trade API)."""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "trading_bot.server:app",
        host=os.environ.get("BOT_HOST", "0.0.0.0"),
        port=int(os.environ.get("BOT_PORT", "8000")),
    )

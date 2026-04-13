from __future__ import annotations

from datetime import datetime
from typing import Any

import discord

from ui import embeds
from utils import config


async def log_event(bot: discord.Client, action: str, details: dict[str, Any], *, level: str = "INFO") -> None:
    payload = dict(details)
    payload.setdefault("level", level)
    payload.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")
    embed = embeds.bot_log_embed(action, payload)
    ch = await config.get_channel(bot, "channel_bot_logs")
    if ch is not None:
        try:
            await ch.send(embed=embed)
            return
        except discord.HTTPException:
            pass

    # Fallback in case log channel is unavailable.
    print(f"[{level}] {action}: {payload}")

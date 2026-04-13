from __future__ import annotations

import discord

from database import db


async def get_rate(key: str) -> int:
    v = await db.get_config(key)
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


async def get_channel(bot: discord.Client, key: str) -> discord.TextChannel | None:
    cid = await db.get_config(key)
    if not cid:
        return None
    try:
        iid = int(cid)
    except ValueError:
        return None
    try:
        ch = bot.get_channel(iid)
        if isinstance(ch, discord.TextChannel):
            return ch
        if ch is None:
            ch = await bot.fetch_channel(iid)
        if isinstance(ch, discord.TextChannel):
            return ch
    except (discord.HTTPException, ValueError):
        return None
    return None


async def get_role(guild: discord.Guild, key: str) -> discord.Role | None:
    rid = await db.get_config(key)
    if not rid:
        return None
    try:
        return guild.get_role(int(rid))
    except ValueError:
        return None


async def get_feature_list() -> list[str]:
    raw = await db.get_config("feature_list")
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not any(l.lower() == "other" for l in lines):
        lines.append("Other")
    return lines

from __future__ import annotations

import os

import discord

from database import db
from utils import config

OWNER_ID = int(os.getenv("OWNER_ID", "0"))


async def is_owner(interaction: discord.Interaction) -> bool:
    return interaction.user is not None and interaction.user.id == OWNER_ID


async def is_admin(interaction: discord.Interaction) -> bool:
    if await is_owner(interaction):
        return True
    if interaction.guild is None:
        return False
    role = await config.get_role(interaction.guild, "role_admin")
    if role is None:
        return False
    member = interaction.user
    if not isinstance(member, discord.Member):
        member = interaction.guild.get_member(interaction.user.id)
    if member is None:
        return False
    return role in member.roles


async def is_registered(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        return False
    tester_role = await config.get_role(interaction.guild, "role_tester")
    if tester_role is None:
        return False
    member = interaction.user
    if not isinstance(member, discord.Member):
        member = interaction.guild.get_member(interaction.user.id)
    if member is None or tester_role not in member.roles:
        return False
    uid = str(interaction.user.id)
    row = await db.get_tester(uid)
    return row is not None


async def is_active_tester(interaction: discord.Interaction) -> bool:
    if not await is_registered(interaction):
        return False
    row = await db.get_tester(str(interaction.user.id))
    return row is not None and int(row.get("is_active", 0)) == 1


async def check_daily_bug_limit(user_id: str, today) -> bool:
    limit = await config.get_rate("daily_bug_limit")
    counts = await db.get_daily_counts(user_id, today)
    return int(counts.get("bugs_today") or 0) < limit


async def check_daily_suggestion_limit(user_id: str, today) -> bool:
    limit = await config.get_rate("daily_suggestion_limit")
    counts = await db.get_daily_counts(user_id, today)
    return int(counts.get("suggestions_today") or 0) < limit


async def check_weekly_cap(user_id: str, week_start, *, next_add: int = 0) -> bool:
    """True if current weekly total + next_add stays at or under the weekly cap."""
    cap = await config.get_rate("weekly_cap")
    current = await db.get_weekly_total(user_id, week_start)
    return current + next_add <= cap

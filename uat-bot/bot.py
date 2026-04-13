from __future__ import annotations

import os
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

from database.db import init_db

load_dotenv(Path(__file__).resolve().parent / ".env")

INTENTS = discord.Intents(
    guilds=True,
    members=True,
    message_content=True,
)


class UATBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=INTENTS)

    async def setup_hook(self) -> None:
        await init_db()
        await self.load_extension("cogs.setup")
        await self.load_extension("cogs.registration")
        await self.load_extension("cogs.bugs")
        await self.load_extension("cogs.suggestions")
        await self.load_extension("cogs.earnings")

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user} (id={self.user.id})")
        synced = await self.tree.sync()
        print(f"Synced {len(synced)} application command(s).")


def main() -> None:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set BOT_TOKEN in .env")
    UATBot().run(token)


if __name__ == "__main__":
    main()

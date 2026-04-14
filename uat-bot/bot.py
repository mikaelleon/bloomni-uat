from __future__ import annotations

import os
import traceback
from pathlib import Path
import logging

import discord
from discord.errors import ConnectionClosed, LoginFailure
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from aiohttp.client_exceptions import ClientConnectorDNSError

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
        self.sync_guild_id = os.getenv("SYNC_GUILD_ID", "").strip()

    async def setup_hook(self) -> None:
        await init_db()
        await self.load_extension("cogs.setup")
        await self.load_extension("cogs.registration")
        await self.load_extension("cogs.bugs")
        await self.load_extension("cogs.suggestions")
        await self.load_extension("cogs.earnings")
        await self.load_extension("cogs.changelog_listener")

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user} (id={self.user.id})")
        try:
            if self.sync_guild_id:
                guild = discord.Object(id=int(self.sync_guild_id))
                # Copy all registered global commands into this guild for
                # fast dev sync/iteration.
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                print(
                    f"Synced {len(synced)} application command(s) to guild "
                    f"{self.sync_guild_id}."
                )
            else:
                synced = await self.tree.sync()
                print(f"Synced {len(synced)} global application command(s).")
        except ValueError:
            print(
                "SYNC_GUILD_ID is not a valid integer. "
                "Skipping guild-only sync and using global sync instead."
            )
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} global application command(s).")

    async def on_resumed(self) -> None:
        print("Gateway session resumed after temporary network interruption.")

    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        print(f"[EVENT_ERROR] event={event_method}")
        print(traceback.format_exc())

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        print(
            f"[APP_CMD_ERROR] command={getattr(interaction.command, 'qualified_name', 'unknown')} "
            f"user_id={getattr(interaction.user, 'id', 'unknown')} "
            f"guild_id={getattr(interaction.guild, 'id', 'dm')}"
        )
        print("".join(traceback.format_exception(type(error), error, error.__traceback__)))
        try:
            msg = (
                "That action failed. Please try again.\n"
                "If it keeps failing, ask the owner to check bot logs."
            )
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            pass


class _DiscordDNSNoiseFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Suppress known transient DNS reconnect tracebacks; Discord retries automatically.
        if record.exc_info and record.exc_info[1]:
            exc = record.exc_info[1]
            if isinstance(exc, ClientConnectorDNSError):
                return False
        return True


def _configure_runtime_logging() -> None:
    logging.getLogger("discord.client").addFilter(_DiscordDNSNoiseFilter())


def main() -> None:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "BOT_TOKEN is missing. Add it to uat-bot/.env and run again."
        )

    try:
        _configure_runtime_logging()
        UATBot().run(token)
    except KeyboardInterrupt:
        raise SystemExit("Bot stopped by user.")
    except LoginFailure:
        raise SystemExit(
            "Discord rejected BOT_TOKEN. "
            "Suggestion: reset bot token in Discord Developer Portal, "
            "update uat-bot/.env, then restart bot.py."
        )
    except ConnectionClosed as exc:
        if getattr(exc, "code", None) == 4004:
            raise SystemExit(
                "Discord closed the connection with code 4004 "
                "(authentication failed). Suggestion: ensure BOT_TOKEN is "
                "current after token reset and retry."
            )
        raise


if __name__ == "__main__":
    main()

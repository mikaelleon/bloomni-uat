"""Optional HTTP listener for GitHub push webhooks (see /config changes)."""

from __future__ import annotations

from discord.ext import commands

from utils.changes_http import start_changes_server, stop_changes_server


class ChangelogListener(commands.Cog):
    """Starts aiohttp when CHANGELOG_HTTP_ENABLED is set in the environment."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._http: tuple | None = None

    async def cog_load(self) -> None:
        self._http = await start_changes_server(self.bot)

    async def cog_unload(self) -> None:
        await stop_changes_server(self._http)
        self._http = None


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ChangelogListener(bot))

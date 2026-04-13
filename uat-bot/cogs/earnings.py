from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from database import db
from ui import embeds
from utils import config
from utils.checks import is_active_tester, is_admin
from utils.time_utils import get_week_start, today_pht


class Earnings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="earnings", description="View weekly earnings")
    @app_commands.describe(user="User (admins only)")
    async def earnings(self, interaction: discord.Interaction, user: discord.User | None = None) -> None:
        target = user or interaction.user
        if user is not None and user.id != interaction.user.id:
            if not await is_admin(interaction):
                await interaction.response.send_message(
                    embed=embeds.error_embed("Only admins can view other users."),
                    ephemeral=True,
                )
                return
        else:
            if not await is_active_tester(interaction):
                await interaction.response.send_message(
                    embed=embeds.error_embed("You need to register first."),
                    ephemeral=True,
                )
                return
        uid = str(target.id)
        tester = await db.get_tester(uid)
        if not tester:
            await interaction.response.send_message(
                embed=embeds.error_embed("Not registered."),
                ephemeral=True,
            )
            return
        ws = get_week_start(today_pht())
        row = await db.get_or_create_earnings(uid, ws)
        cfg = await db.get_all_config()
        br = int(row.get("bugs_submitted") or 0)
        bres = int(row.get("bugs_resolved") or 0)
        ss = int(row.get("suggestions_submitted") or 0)
        si = int(row.get("suggestions_implemented") or 0)
        r_bug = await config.get_rate("bug_report_rate")
        r_res = await config.get_rate("bug_resolve_bonus")
        r_sug = await config.get_rate("suggestion_submit_rate")
        r_imp = await config.get_rate("suggestion_implement_bonus")
        earn_bug_sub = br * r_bug
        earn_bug_res = bres * r_res
        earn_sug_sub = ss * r_sug
        earn_sug_imp = si * r_imp
        total = int(row.get("total_earned") or 0)
        cap = await config.get_rate("weekly_cap")
        paid = bool(int(row.get("is_paid") or 0))
        week_label = f"{ws.isoformat()} (week start)"
        e = embeds.earnings_embed_detailed(
            tester.get("display_name", "?"),
            week_label,
            br,
            bres,
            ss,
            si,
            earn_bug_sub,
            earn_bug_res,
            earn_sug_sub,
            earn_sug_imp,
            total,
            cap,
            paid,
        )
        await interaction.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="rates", description="Show current rates and limits")
    async def rates(self, interaction: discord.Interaction) -> None:
        cfg = await db.get_all_config()
        await interaction.response.send_message(embed=embeds.rates_embed(cfg), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Earnings(bot))

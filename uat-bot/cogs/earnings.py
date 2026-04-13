from __future__ import annotations

from datetime import datetime, time, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from database import db
from ui import embeds
from ui.views import PaginationView
from utils import config
from utils.checks import is_active_tester, is_admin
from utils.time_utils import PHT, get_week_start, now_pht, today_pht


class Earnings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _next_daily_reset_unix(self) -> int:
        now = now_pht()
        nxt = PHT.localize(datetime.combine(now.date() + timedelta(days=1), time.min))
        return int(nxt.timestamp())

    def _next_weekly_reset_unix(self) -> int:
        ws = get_week_start(today_pht())
        nxt = PHT.localize(datetime.combine(ws + timedelta(days=7), time.min))
        return int(nxt.timestamp())

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
        bv = int(row.get("bugs_validated") or 0)
        bres = int(row.get("bugs_resolved") or 0)
        ss = int(row.get("suggestions_submitted") or 0)
        sa = int(row.get("suggestions_acknowledged") or 0)
        si = int(row.get("suggestions_implemented") or 0)
        r_bug = await config.get_rate("bug_report_rate")
        r_res = await config.get_rate("bug_resolve_bonus")
        r_sug = await config.get_rate("suggestion_submit_rate")
        r_imp = await config.get_rate("suggestion_implement_bonus")
        earn_bug_sub = bv * r_bug
        earn_bug_res = bres * r_res
        earn_sug_sub = sa * r_sug
        earn_sug_imp = si * r_imp
        total = int(row.get("total_earned") or 0)
        cap = await config.get_rate("weekly_cap")
        paid = bool(int(row.get("is_paid") or 0))
        week_label = f"{ws.isoformat()} (week start)"
        e = embeds.earnings_embed_detailed(
            tester.get("display_name", "?"),
            week_label,
            br,
            bv,
            bres,
            ss,
            sa,
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

    @app_commands.command(name="myinfo", description="Your tester profile and live countdowns")
    async def myinfo(self, interaction: discord.Interaction) -> None:
        if not await is_active_tester(interaction):
            await interaction.response.send_message(embed=embeds.error_embed("You need to register first."), ephemeral=True)
            return
        uid = str(interaction.user.id)
        tester = await db.get_tester(uid)
        if not tester:
            await interaction.response.send_message(embed=embeds.error_embed("Not registered."), ephemeral=True)
            return
        today = today_pht()
        ws = get_week_start(today)
        dc = await db.get_daily_counts(uid, today)
        weekly = await db.get_or_create_earnings(uid, ws)
        all_time = await db.get_tester_all_time_stats(uid)
        pending_bugs = len(await db.get_user_bugs(uid, "submitted"))
        pending_suggestions = len(await db.get_user_suggestions(uid, "submitted"))
        senior = "✅ Yes" if int(tester.get("weeks_active") or 0) >= 4 else "❌ No"
        daily_reset = self._next_daily_reset_unix()
        weekly_reset = self._next_weekly_reset_unix()
        r_bug = await config.get_rate("bug_report_rate")
        r_sug = await config.get_rate("suggestion_submit_rate")
        daily_bug_limit = await config.get_rate("daily_bug_limit")
        daily_suggestion_limit = await config.get_rate("daily_suggestion_limit")
        weekly_cap = await config.get_rate("weekly_cap")
        e = discord.Embed(
            title=f"🧪 Tester Profile — {tester.get('display_name', interaction.user.display_name)}",
            color=embeds.EMBED_COLOR,
            description=(
                f"**Discord user:** {interaction.user.mention}\n"
                f"**Registered:** {str(tester.get('registered_at', '—'))[:10]}\n"
                f"**Active:** {'✅ Yes' if int(tester.get('is_active', 0)) else '❌ No'}\n"
                f"**Weeks active:** {tester.get('weeks_active', 0)}\n"
                f"**Senior Tester:** {senior}"
            ),
        )
        e.add_field(
            name="Today's Usage",
            value=(
                f"Bugs submitted: {dc.get('bugs_today', 0)} / {daily_bug_limit}\n"
                f"Suggestions submitted: {dc.get('suggestions_today', 0)} / {daily_suggestion_limit}\n\n"
                f"⏰ Daily reset: <t:{daily_reset}:R>"
            ),
            inline=False,
        )
        e.add_field(
            name="This Week",
            value=(
                f"Earnings so far: ₱{weekly.get('total_earned', 0)} / ₱{weekly_cap}\n"
                f"Bugs submitted: {pending_bugs} (₱{pending_bugs * r_bug} pending validation)\n"
                f"Bugs validated: {weekly.get('bugs_validated', 0)}\n"
                f"Bugs resolved: {weekly.get('bugs_resolved', 0)}\n"
                f"Suggestions submitted: {pending_suggestions} (₱{pending_suggestions * r_sug} pending acknowledgement)\n"
                f"Suggestions acknowledged: {weekly.get('suggestions_acknowledged', 0)}\n\n"
                f"⏰ Weekly reset & payout: <t:{weekly_reset}:R>"
            ),
            inline=False,
        )
        e.add_field(
            name="All-time Stats",
            value=(
                f"Total bugs submitted: {all_time.get('bugs_submitted', 0)}\n"
                f"Total bugs validated: {all_time.get('bugs_validated', 0)}\n"
                f"Total bugs resolved: {all_time.get('bugs_resolved', 0)}\n"
                f"Total suggestions submitted: {all_time.get('suggestions_submitted', 0)}\n"
                f"Total suggestions acknowledged: {all_time.get('suggestions_acknowledged', 0)}\n"
                f"Total suggestions implemented: {all_time.get('suggestions_implemented', 0)}\n"
                f"Total earned (all-time): ₱{all_time.get('total_earned_all_time', 0)}"
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="mybugs", description="List your bugs by status")
    @app_commands.describe(status="Filter by your bug status")
    async def mybugs(self, interaction: discord.Interaction, status: str = "all") -> None:
        if not await is_active_tester(interaction):
            await interaction.response.send_message(embed=embeds.error_embed("You need to register first."), ephemeral=True)
            return
        rows = await db.get_user_bugs(str(interaction.user.id), status)
        if not rows:
            await interaction.response.send_message(embed=embeds.error_embed("No bugs found for that filter."), ephemeral=True)
            return
        lines = [f"**{b['bug_id']}** — {b['status']} — {b['title'][:70]}" for b in rows]
        pages: list[discord.Embed] = []
        chunk = 8
        total_pages = max(1, (len(lines) + chunk - 1) // chunk)
        for i in range(0, len(lines), chunk):
            e = discord.Embed(title=f"My Bugs ({status})", description="\n".join(lines[i:i + chunk]), color=embeds.EMBED_COLOR)
            e.set_footer(text=f"Page {len(pages) + 1}/{total_pages}")
            pages.append(e)
        view = PaginationView(author_id=interaction.user.id, pages=pages)
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @app_commands.command(name="mysuggestions", description="List your suggestions by status")
    @app_commands.describe(status="Filter by your suggestion status")
    async def mysuggestions(self, interaction: discord.Interaction, status: str = "all") -> None:
        if not await is_active_tester(interaction):
            await interaction.response.send_message(embed=embeds.error_embed("You need to register first."), ephemeral=True)
            return
        rows = await db.get_user_suggestions(str(interaction.user.id), status)
        if not rows:
            await interaction.response.send_message(embed=embeds.error_embed("No suggestions found for that filter."), ephemeral=True)
            return
        lines = [f"**{s['suggestion_id']}** — {s['status']} — {s['title'][:70]}" for s in rows]
        pages: list[discord.Embed] = []
        chunk = 8
        total_pages = max(1, (len(lines) + chunk - 1) // chunk)
        for i in range(0, len(lines), chunk):
            e = discord.Embed(title=f"My Suggestions ({status})", description="\n".join(lines[i:i + chunk]), color=embeds.EMBED_COLOR)
            e.set_footer(text=f"Page {len(pages) + 1}/{total_pages}")
            pages.append(e)
        view = PaginationView(author_id=interaction.user.id, pages=pages)
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @app_commands.command(name="mypending", description="Quick view of items awaiting owner action")
    async def mypending(self, interaction: discord.Interaction) -> None:
        if not await is_active_tester(interaction):
            await interaction.response.send_message(embed=embeds.error_embed("You need to register first."), ephemeral=True)
            return
        uid = str(interaction.user.id)
        bugs = await db.get_user_bugs(uid, "submitted")
        sugs = await db.get_user_suggestions(uid, "submitted")
        desc = (
            f"Pending bug validations: **{len(bugs)}**\n"
            f"Pending suggestion acknowledgements: **{len(sugs)}**"
        )
        await interaction.response.send_message(embed=discord.Embed(title="My Pending Queue", description=desc, color=embeds.EMBED_COLOR), ephemeral=True)

    @app_commands.command(name="streak", description="Show active-week streak progress")
    async def streak(self, interaction: discord.Interaction) -> None:
        if not await is_active_tester(interaction):
            await interaction.response.send_message(embed=embeds.error_embed("You need to register first."), ephemeral=True)
            return
        tester = await db.get_tester(str(interaction.user.id))
        if not tester:
            await interaction.response.send_message(embed=embeds.error_embed("Not registered."), ephemeral=True)
            return
        weeks = int(tester.get("weeks_active") or 0)
        consecutive = int(tester.get("consecutive_weeks") or 0)
        target = 4
        desc = (
            f"Consecutive active weeks: **{consecutive}**\n"
            f"Total active weeks: **{weeks}**\n"
            f"Senior progress: **{min(weeks, target)}/{target}**\n"
            f"Senior status: {'✅ Unlocked' if weeks >= target else '⏳ In progress'}"
        )
        await interaction.response.send_message(embed=discord.Embed(title="Tester Streak", description=desc, color=embeds.EMBED_COLOR), ephemeral=True)

    @app_commands.command(name="history", description="View your weekly earnings history")
    @app_commands.describe(week="0 for this week, 1 for last week, etc.")
    async def history(self, interaction: discord.Interaction, week: int | None = None) -> None:
        if not await is_active_tester(interaction):
            await interaction.response.send_message(embed=embeds.error_embed("You need to register first."), ephemeral=True)
            return
        rows = await db.get_earnings_history(str(interaction.user.id), limit=16)
        if not rows:
            await interaction.response.send_message(embed=embeds.error_embed("No earnings history yet."), ephemeral=True)
            return
        if week is not None and 0 <= week < len(rows):
            rows = [rows[week]]
        lines = [f"Week {r['week_start']}: ₱{r['total_earned']} ({'paid' if int(r.get('is_paid') or 0) else 'pending'})" for r in rows[:10]]
        await interaction.response.send_message(embed=discord.Embed(title="Earnings History", description="\n".join(lines), color=embeds.EMBED_COLOR), ephemeral=True)

    @app_commands.command(name="leaderboard", description="Top testers this week by validated earnings")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        ws = get_week_start(today_pht())
        rows = await db.get_weekly_leaderboard(ws, limit=10)
        if not rows:
            await interaction.response.send_message(embed=embeds.error_embed("No earnings yet this week."), ephemeral=True)
            return
        lines: list[str] = []
        for idx, row in enumerate(rows, start=1):
            tester = await db.get_tester(row["user_id"])
            name = tester.get("display_name", row["user_id"]) if tester else row["user_id"]
            lines.append(f"{idx}. **{name}** — ₱{row.get('total_earned', 0)}")
        await interaction.response.send_message(embed=discord.Embed(title="Weekly Leaderboard", description="\n".join(lines), color=embeds.EMBED_COLOR), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Earnings(bot))

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from database import db
from ui import embeds
from ui.modals import BugReportModal, BugReopenModal
from ui.views import PaginationView
from utils import config
from utils.checks import check_daily_bug_limit, check_weekly_cap, is_active_tester, is_owner
from utils.time_utils import get_week_start, now_pht, today_pht
from utils.logging import log_event


def _jaccard(a: str, b: str) -> float:
    sa = set(a.lower().split())
    sb = set(b.lower().split())
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


class BugReportModalImpl(BugReportModal):
    def __init__(self, cog: "Bugs", severity: str):
        super().__init__()
        self.cog = cog
        self.severity = severity

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_bug_modal(
            interaction,
            self.severity,
            str(self.bug_title.value),
            str(self.steps.value),
            str(self.actual.value),
            str(self.expected.value),
        )


class BugReopenModalImpl(BugReopenModal):
    def __init__(self, cog: "Bugs", bug: dict):
        super().__init__()
        self.cog = cog
        self.bug = bug

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.process_bug_reopen(interaction, self.bug, str(self.reason.value or ""))


class DuplicateConfirmView(discord.ui.View):
    def __init__(self, cog: "Bugs", payload: dict, author_id: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.payload = payload
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message("Not your confirmation.", ephemeral=True)
        return False

    @discord.ui.button(label="This is different, submit anyway", style=discord.ButtonStyle.success)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        for c in self.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True
        await interaction.response.edit_message(view=self)
        await self.cog.finalize_bug_submission(interaction, self.payload)

    @discord.ui.button(label="Cancel, it's a duplicate", style=discord.ButtonStyle.danger)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        for c in self.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True
        await interaction.response.edit_message(content="Cancelled.", embed=None, view=self)


class SeverityBugView(discord.ui.View):
    def __init__(self, cog: "Bugs"):
        super().__init__(timeout=180)
        self.cog = cog
        self.select = discord.ui.Select(
            placeholder="Select severity level",
            options=[
                discord.SelectOption(
                    label="High — Core functionality broken",
                    value="high",
                    emoji="🔴",
                ),
                discord.SelectOption(
                    label="Medium — Feature partially broken",
                    value="medium",
                    emoji="🟡",
                ),
                discord.SelectOption(
                    label="Low — Minor issue or cosmetic",
                    value="low",
                    emoji="🟢",
                ),
            ],
        )
        self.select.callback = self._on_select
        self.add_item(self.select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        sev = str(self.select.values[0])
        await interaction.response.send_modal(BugReportModalImpl(self.cog, sev))


class Bugs(commands.Cog):
    bugs = app_commands.Group(name="bugs", description="Bug tracking (resolve, list, ...)")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="bug", description="Submit a bug report")
    async def bug(self, interaction: discord.Interaction) -> None:
        await self._bug_start(interaction)

    @bugs.command(name="submit", description="Submit a bug report")
    async def bug_submit(self, interaction: discord.Interaction) -> None:
        await self._bug_start(interaction)

    async def _bug_start(self, interaction: discord.Interaction) -> None:
        if not await is_active_tester(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("You need to register first. Head to #register-here."),
                ephemeral=True,
            )
            return
        uid = str(interaction.user.id)
        today = today_pht()
        ws = get_week_start(today)
        if not await check_daily_bug_limit(uid, today):
            await interaction.response.send_message(
                embed=embeds.error_embed(
                    "You've hit today's bug limit (3/day). Come back tomorrow!"
                ),
                ephemeral=True,
            )
            return
        rate = await config.get_rate("bug_report_rate")
        if not await check_weekly_cap(uid, ws, next_add=rate):
            await interaction.response.send_message(
                embed=embeds.error_embed(
                    "You've reached the weekly earnings cap (₱250). See you next week!"
                ),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            "Choose severity, then fill out the bug form.",
            view=SeverityBugView(self),
            ephemeral=True,
        )

    async def handle_bug_modal(
        self,
        interaction: discord.Interaction,
        severity: str,
        title: str,
        steps: str,
        actual: str,
        expected: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        titles = await db.get_all_open_bug_titles()
        dups = [t for t in titles if _jaccard(title, t) >= 0.7]
        payload = {
            "severity": severity,
            "title": title,
            "steps": steps,
            "actual": actual,
            "expected": expected,
        }
        if dups:
            emb = discord.Embed(
                title="Possible duplicate(s)",
                description="Similar open bug titles:\n" + "\n".join(f"• {d}" for d in dups[:10]),
                color=embeds.EMBED_COLOR,
            )
            view = DuplicateConfirmView(self, payload, interaction.user.id)
            await interaction.followup.send(embed=emb, view=view, ephemeral=True)
            return
        await self.finalize_bug_submission(interaction, payload)

    async def finalize_bug_submission(self, interaction: discord.Interaction, payload: dict) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        today = today_pht()
        ws = get_week_start(today)
        rate = await config.get_rate("bug_report_rate")
        if not await check_weekly_cap(uid, ws, next_add=rate):
            await interaction.followup.send(
                embed=embeds.error_embed("Weekly cap reached."),
                ephemeral=True,
            )
            return
        bug_id = await db.get_next_bug_id()
        submitted = now_pht()
        await db.create_bug(
            bug_id,
            uid,
            payload["title"],
            payload["steps"],
            payload["actual"],
            payload["expected"],
            payload["severity"],
            submitted,
        )
        ch = await config.get_channel(self.bot, "channel_bug_reports")
        if not ch:
            await interaction.followup.send(
                embed=embeds.error_embed("Bug reports channel is not configured."),
                ephemeral=True,
            )
            return
        reporter = interaction.user
        bug_row = await db.get_bug(bug_id)
        assert bug_row
        msg = await ch.send(embed=embeds.bug_report_embed(bug_row, reporter))
        await db.update_bug_message_id(bug_id, str(msg.id))
        thread_name = f"{bug_id} — {payload['title']}"[:100]
        thread = await msg.create_thread(name=thread_name)
        await db.update_bug_thread(bug_id, str(thread.id))
        await thread.send(
            "📎 **Attach your evidence here.**\n"
            "Screenshots, screen recordings, or any other files that help reproduce this bug. "
            "This thread is also where any discussion about this bug happens."
        )
        await db.add_earnings(uid, ws, "bugs_submitted", 1)
        await db.add_earnings(uid, ws, "total_earned", rate)
        await db.increment_daily_count(uid, today, "bugs_today")
        jump = thread.jump_url
        dm = discord.Embed(
            title=f"Bug {bug_id} submitted",
            description=(
                f"**Title:** {payload['title']}\n"
                f"**Severity:** {payload['severity']}\n"
                f"**Thread:** {jump}\n"
                f"+₱{rate} added to your weekly earnings."
            ),
            color=embeds.EMBED_COLOR,
        )
        try:
            await interaction.user.send(embed=dm)
        except discord.HTTPException:
            pass
        await interaction.followup.send(
            embed=embeds.success_embed(f"Bug {bug_id} submitted! Check your DMs for the thread link."),
            ephemeral=True,
        )
        await log_event(
            self.bot,
            "BUG_SUBMIT",
            {"bug_id": bug_id, "user_id": uid, "timestamp": submitted.isoformat()},
        )

    @bugs.command(name="resolve", description="Mark a bug as resolved")
    @app_commands.describe(bug_id="Bug ID e.g. BUG-001")
    async def bug_resolve(self, interaction: discord.Interaction, bug_id: str) -> None:
        if not await is_owner(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Only the bot owner can use this."),
                ephemeral=True,
            )
            return
        bug = await db.get_bug(bug_id)
        if not bug:
            await interaction.response.send_message(
                embed=embeds.error_embed("Bug ID not found."),
                ephemeral=True,
            )
            return
        if bug.get("status") != "open":
            await interaction.response.send_message(
                embed=embeds.error_embed("This bug is already resolved."),
                ephemeral=True,
            )
            return
        bonus = await config.get_rate("bug_resolve_bonus")
        reporter = await self.bot.fetch_user(int(bug["reporter_id"]))
        view = discord.ui.View(timeout=60)

        async def confirm(i: discord.Interaction) -> None:
            if i.user.id != interaction.user.id:
                await i.response.send_message("Not for you.", ephemeral=True)
                return
            await i.response.defer(ephemeral=True)
            await db.update_bug_status(bug["bug_id"], "resolved", resolved_at=now_pht())
            br_ch = await config.get_channel(self.bot, "channel_bug_reports")
            if br_ch and bug.get("message_id"):
                try:
                    m = await br_ch.fetch_message(int(bug["message_id"]))
                    b2 = await db.get_bug(bug["bug_id"])
                    rep = await self.bot.fetch_user(int(b2["reporter_id"]))
                    await m.edit(embed=embeds.bug_report_embed(b2, rep))
                except discord.HTTPException:
                    pass
            if bug.get("thread_id"):
                try:
                    th = await self.bot.fetch_channel(int(bug["thread_id"]))
                    if isinstance(th, discord.Thread):
                        await th.edit(archived=True)
                except discord.HTTPException:
                    pass
            rid = bug["reporter_id"]
            ws = get_week_start(today_pht())
            await db.add_earnings(rid, ws, "bugs_resolved", 1)
            await db.add_earnings(rid, ws, "total_earned", bonus)
            total = await db.get_weekly_total(rid, ws)
            cap = await config.get_rate("weekly_cap")
            tester = await db.get_tester(rid)
            name = tester.get("display_name", "?") if tester else "?"
            payout_ch = await config.get_channel(self.bot, "channel_payout_log")
            if payout_ch:
                await payout_ch.send(
                    f"✅ {bug['bug_id']} resolved! +₱{bonus} bonus credited to {name}. "
                    f"Weekly total: ₱{total} / ₱{cap}"
                )
            try:
                await reporter.send(
                    f"Your bug {bug['bug_id']} has been marked as resolved! +₱{bonus} bonus added to your earnings. 🎉"
                )
            except discord.HTTPException:
                pass
            await log_event(
                self.bot,
                "BUG_RESOLVE",
                {"bug_id": bug["bug_id"], "by": str(interaction.user.id)},
            )
            await i.followup.send(embed=embeds.success_embed("Bug marked resolved."), ephemeral=True)

        async def cancel(i: discord.Interaction) -> None:
            if i.user.id != interaction.user.id:
                await i.response.send_message("Not for you.", ephemeral=True)
                return
            await i.response.send_message("Cancelled.", ephemeral=True)

        b1 = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.success)
        b2 = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger)
        b1.callback = confirm
        b2.callback = cancel
        view.add_item(b1)
        view.add_item(b2)
        await interaction.response.send_message(
            embed=embeds.confirmation_embed(
                "Confirm resolve",
                f"Mark {bug['bug_id']} as resolved? This will credit +₱{bonus} to {reporter.display_name}.",
            ),
            view=view,
            ephemeral=True,
        )

    @bugs.command(name="list", description="List bugs")
    @app_commands.describe(status="Filter by status")
    @app_commands.choices(
        status=[
            app_commands.Choice(name="open", value="open"),
            app_commands.Choice(name="resolved", value="resolved"),
            app_commands.Choice(name="duplicate", value="duplicate"),
            app_commands.Choice(name="all", value="all"),
        ]
    )
    async def bug_list(
        self,
        interaction: discord.Interaction,
        status: str,
    ) -> None:
        if not await is_active_tester(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("You need to register first."),
                ephemeral=True,
            )
            return
        bugs = await db.get_bugs_by_status(status)
        if not bugs:
            await interaction.response.send_message(embed=embeds.error_embed("No bugs found."), ephemeral=True)
            return
        lines: list[str] = []
        for b in bugs:
            t = await db.get_tester(b["reporter_id"])
            dn = t.get("display_name", "?") if t else "?"
            lines.append(
                f"**{b['bug_id']}** — {b['title'][:80]} — {b['severity']} — {dn} — {b['submitted_at']}"
            )
        chunk = 5
        pages: list[discord.Embed] = []
        total_pages = max(1, (len(lines) + chunk - 1) // chunk)
        for i in range(0, len(lines), chunk):
            e = discord.Embed(
                title=f"Bugs ({status})",
                description="\n".join(lines[i : i + chunk]),
                color=embeds.EMBED_COLOR,
            )
            e.set_footer(text=f"Page {len(pages) + 1}/{total_pages}")
            pages.append(e)
        view = PaginationView(author_id=interaction.user.id, pages=pages)
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)
        msg = await interaction.original_response()
        view.message = msg

    @bugs.command(name="info", description="Show bug details")
    @app_commands.describe(bug_id="Bug ID")
    async def bug_info(self, interaction: discord.Interaction, bug_id: str) -> None:
        if not await is_active_tester(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("You need to register first."),
                ephemeral=True,
            )
            return
        bug = await db.get_bug(bug_id)
        if not bug:
            await interaction.response.send_message(
                embed=embeds.error_embed("Bug not found."),
                ephemeral=True,
            )
            return
        u = await self.bot.fetch_user(int(bug["reporter_id"]))
        e = embeds.bug_report_embed(bug, u)
        if bug.get("thread_id"):
            try:
                th = await self.bot.fetch_channel(int(bug["thread_id"]))
                if isinstance(th, discord.Thread):
                    e.description = (e.description or "") + f"\n**Thread:** {th.jump_url}"
            except discord.HTTPException:
                pass
        await interaction.response.send_message(embed=e, ephemeral=True)

    @bugs.command(name="reopen", description="Reopen a resolved bug")
    @app_commands.describe(bug_id="Bug ID")
    async def bug_reopen(self, interaction: discord.Interaction, bug_id: str) -> None:
        if not await is_owner(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Only the bot owner can use this."),
                ephemeral=True,
            )
            return
        bug = await db.get_bug(bug_id)
        if not bug or bug.get("status") != "resolved":
            await interaction.response.send_message(
                embed=embeds.error_embed("Bug not found or not resolved."),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(BugReopenModalImpl(self, bug))

    async def process_bug_reopen(
        self, interaction: discord.Interaction, bug: dict, reason: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        await db.update_bug_status(bug["bug_id"], "open", resolved_at=None)
        br_ch = await config.get_channel(self.bot, "channel_bug_reports")
        if br_ch and bug.get("message_id"):
            try:
                m = await br_ch.fetch_message(int(bug["message_id"]))
                b2 = await db.get_bug(bug["bug_id"])
                rep = await self.bot.fetch_user(int(b2["reporter_id"]))
                await m.edit(embed=embeds.bug_report_embed(b2, rep))
            except discord.HTTPException:
                pass
        if bug.get("thread_id"):
            try:
                th = await self.bot.fetch_channel(int(bug["thread_id"]))
                if isinstance(th, discord.Thread):
                    await th.edit(archived=False)
            except discord.HTTPException:
                pass
        rid = bug["reporter_id"]
        ws = get_week_start(today_pht())
        bonus = await config.get_rate("bug_resolve_bonus")
        await db.add_earnings(rid, ws, "bugs_resolved", -1)
        await db.add_earnings(rid, ws, "total_earned", -bonus)
        try:
            u = await self.bot.fetch_user(int(rid))
            msg = f"Your bug {bug['bug_id']} was reopened."
            if reason.strip():
                msg += f" Reason: {reason.strip()}"
            await u.send(msg)
        except discord.HTTPException:
            pass
        await log_event(
            self.bot,
            "BUG_REOPEN",
            {"bug_id": bug["bug_id"], "by": str(interaction.user.id)},
        )
        await interaction.followup.send(embed=embeds.success_embed("Bug reopened."), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Bugs(bot))






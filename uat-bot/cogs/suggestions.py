from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from database import db
from ui import embeds
from ui.modals import SuggestionDismissModal, SuggestionModal
from ui.views import PaginationView
from utils import config
from utils.checks import check_daily_suggestion_limit, check_weekly_cap, is_active_tester, is_owner
from utils.time_utils import get_week_start, now_pht, today_pht
from utils.logging import log_event


class SuggestionModalImpl(SuggestionModal):
    def __init__(self, cog: "Suggestions", feature_tag: str):
        super().__init__()
        self.cog = cog
        self.feature_tag = feature_tag

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_suggestion_modal(
            interaction,
            self.feature_tag,
            str(self.title_field.value),
            str(self.description.value),
        )


class SuggestionDismissModalImpl(SuggestionDismissModal):
    def __init__(self, cog: "Suggestions", suggestion_id: str):
        super().__init__()
        self.cog = cog
        self.suggestion_id = suggestion_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.process_dismiss(
            interaction, self.suggestion_id, str(self.reason.value or "")
        )


class FeatureSelectView(discord.ui.View):
    def __init__(self, cog: "Suggestions", options: list[str]):
        super().__init__(timeout=180)
        self.cog = cog
        opts = [
            discord.SelectOption(label=o[:100], value=o[:100])
            for o in options[:25]
        ]
        self.select = discord.ui.Select(
            placeholder="Which feature does this relate to?",
            options=opts,
        )
        self.select.callback = self._on_select
        self.add_item(self.select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        tag = str(self.select.values[0])
        await interaction.response.send_modal(SuggestionModalImpl(self.cog, tag))


class Suggestions(commands.Cog):
    suggestion = app_commands.Group(name="suggestion", description="Suggestions (implement, dismiss, ...)")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _earning_dm_embed(self, user_id: str, title: str, detail: str) -> discord.Embed:
        ws = get_week_start(today_pht())
        weekly = await db.get_or_create_earnings(user_id, ws)
        total = int(weekly.get("total_earned") or 0)
        cap = await config.get_rate("weekly_cap")
        dc = await db.get_daily_counts(user_id, today_pht())
        bug_limit = await config.get_rate("daily_bug_limit")
        sug_limit = await config.get_rate("daily_suggestion_limit")
        e = discord.Embed(title=title, description=detail, color=embeds.EMBED_COLOR)
        e.add_field(
            name="Current stats",
            value=(
                f"Weekly balance: ₱{total} / ₱{cap}\n"
                f"Weekly cap remaining: ₱{max(0, cap - total)}\n"
                f"Daily bug slots left: {max(0, bug_limit - int(dc.get('bugs_today', 0)))}\n"
                f"Daily suggestion slots left: {max(0, sug_limit - int(dc.get('suggestions_today', 0)))}"
            ),
            inline=False,
        )
        return e

    @app_commands.command(name="suggest", description="Submit a suggestion")
    async def suggest(self, interaction: discord.Interaction) -> None:
        if not await is_active_tester(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("You need to register first. Head to #register-here."),
                ephemeral=True,
            )
            return
        uid = str(interaction.user.id)
        today = today_pht()
        ws = get_week_start(today)
        if not await check_daily_suggestion_limit(uid, today):
            await interaction.response.send_message(
                embed=embeds.error_embed(
                    "You've hit today's suggestion limit (2/day). Come back tomorrow!"
                ),
                ephemeral=True,
            )
            return
        feats = await config.get_feature_list()
        await interaction.response.send_message(
            "Pick a feature, then describe your suggestion.",
            view=FeatureSelectView(self, feats),
            ephemeral=True,
        )

    async def handle_suggestion_modal(
        self,
        interaction: discord.Interaction,
        feature_tag: str,
        title: str,
        description: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        today = today_pht()
        sid = await db.get_next_suggestion_id()
        submitted = now_pht()
        await db.create_suggestion(sid, uid, feature_tag, title, description, submitted)
        ch = await config.get_channel(self.bot, "channel_suggestions")
        if not ch:
            await interaction.followup.send(
                embed=embeds.error_embed("Suggestions channel is not configured."),
                ephemeral=True,
            )
            return
        row = await db.get_suggestion(sid)
        assert row
        msg = await ch.send(embed=embeds.suggestion_embed(row, interaction.user))
        await db.update_suggestion_message_id(sid, str(msg.id))
        await db.increment_daily_count(uid, today, "suggestions_today")
        dm = discord.Embed(
            title=f"Suggestion {sid}",
            description=(
                f"**Title:** {title}\n"
                f"**Feature:** {feature_tag}\n"
                "Submitted successfully and waiting for owner acknowledgement."
            ),
            color=embeds.EMBED_COLOR,
        )
        try:
            await interaction.user.send(embed=dm)
        except discord.HTTPException:
            pass
        await interaction.followup.send(
            embed=embeds.success_embed(f"Suggestion {sid} submitted! Check your DMs."),
            ephemeral=True,
        )
        await log_event(
            self.bot,
            "SUGGESTION_SUBMIT",
            {"suggestion_id": sid, "user_id": uid, "timestamp": submitted.isoformat()},
        )

    @suggestion.command(name="implement", description="Mark a suggestion as implemented")
    @app_commands.describe(suggestion_id="Suggestion ID e.g. SUG-001")
    async def suggestion_implement(self, interaction: discord.Interaction, suggestion_id: str) -> None:
        if not await is_owner(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Only the bot owner can use this."),
                ephemeral=True,
            )
            return
        sug = await db.get_suggestion(suggestion_id)
        if not sug:
            await interaction.response.send_message(
                embed=embeds.error_embed("Suggestion not found."),
                ephemeral=True,
            )
            return
        if sug.get("status") not in {"acknowledged", "submitted"}:
            await interaction.response.send_message(
                embed=embeds.error_embed("Suggestion must be submitted/acknowledged first."),
                ephemeral=True,
            )
            return
        bonus = await config.get_rate("suggestion_implement_bonus")
        submitter = await self.bot.fetch_user(int(sug["submitter_id"]))
        view = discord.ui.View(timeout=60)

        async def confirm(i: discord.Interaction) -> None:
            if i.user.id != interaction.user.id:
                await i.response.send_message("Not for you.", ephemeral=True)
                return
            await i.response.defer(ephemeral=True)
            await db.update_suggestion_status(
                sug["suggestion_id"], "implemented", actioned_at=now_pht()
            )
            sch = await config.get_channel(self.bot, "channel_suggestions")
            if sch and sug.get("message_id"):
                try:
                    m = await sch.fetch_message(int(sug["message_id"]))
                    s2 = await db.get_suggestion(sug["suggestion_id"])
                    u = await self.bot.fetch_user(int(s2["submitter_id"]))
                    await m.edit(embed=embeds.suggestion_embed(s2, u))
                except discord.HTTPException:
                    pass
            rid = sug["submitter_id"]
            ws = get_week_start(today_pht())
            await db.add_earnings(rid, ws, "suggestions_implemented", 1)
            await db.add_earnings(rid, ws, "total_earned", bonus)
            total = await db.get_weekly_total(rid, ws)
            cap = await config.get_rate("weekly_cap")
            tester = await db.get_tester(rid)
            name = tester.get("display_name", "?") if tester else "?"
            payout_ch = await config.get_channel(self.bot, "channel_payout_log")
            if payout_ch:
                await payout_ch.send(
                    f"✅ {sug['suggestion_id']} implemented! +₱{bonus} credited to {name}. "
                    f"Weekly total: ₱{total} / ₱{cap}"
                )
            try:
                dm = await self._earning_dm_embed(
                    rid,
                    f"Suggestion {sug['suggestion_id']} implemented",
                    f"Your suggestion was implemented. **+₱{bonus}** bonus added to your earnings.",
                )
                await submitter.send(embed=dm)
            except discord.HTTPException:
                pass
            await log_event(
                self.bot,
                "SUGGESTION_IMPLEMENT",
                {"suggestion_id": sug["suggestion_id"], "by": str(interaction.user.id)},
            )
            await i.followup.send(embed=embeds.success_embed("Marked implemented."), ephemeral=True)

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
                "Confirm implement",
                f"Mark {sug['suggestion_id']} as implemented? This will credit +₱{bonus} to {submitter.display_name}.",
            ),
            view=view,
            ephemeral=True,
        )

    @suggestion.command(name="acknowledge", description="Acknowledge a suggestion and credit submitter")
    @app_commands.describe(suggestion_id="Suggestion ID e.g. SUG-001")
    async def suggestion_acknowledge(self, interaction: discord.Interaction, suggestion_id: str) -> None:
        if not await is_owner(interaction):
            await interaction.response.send_message(embed=embeds.error_embed("Only the bot owner can use this."), ephemeral=True)
            return
        sug = await db.get_suggestion(suggestion_id)
        if not sug:
            await interaction.response.send_message(embed=embeds.error_embed("Suggestion not found."), ephemeral=True)
            return
        if sug.get("status") != "submitted":
            await interaction.response.send_message(
                embed=embeds.error_embed("Only submitted suggestions can be acknowledged."),
                ephemeral=True,
            )
            return
        submitter_id = sug["submitter_id"]
        ws = get_week_start(today_pht())
        rate = await config.get_rate("suggestion_submit_rate")
        if not await check_weekly_cap(submitter_id, ws, next_add=rate):
            await interaction.response.send_message(
                embed=embeds.error_embed("Cannot acknowledge: submitter already hit weekly cap."),
                ephemeral=True,
            )
            return
        await db.acknowledge_suggestion(sug["suggestion_id"], now_pht())
        await db.add_earnings(submitter_id, ws, "suggestions_acknowledged", 1)
        await db.add_earnings(submitter_id, ws, "total_earned", rate)
        sch = await config.get_channel(self.bot, "channel_suggestions")
        if sch and sug.get("message_id"):
            try:
                m = await sch.fetch_message(int(sug["message_id"]))
                s2 = await db.get_suggestion(sug["suggestion_id"])
                u = await self.bot.fetch_user(int(s2["submitter_id"]))
                await m.edit(embed=embeds.suggestion_embed(s2, u))
            except discord.HTTPException:
                pass
        try:
            submitter = await self.bot.fetch_user(int(submitter_id))
            dm = await self._earning_dm_embed(
                submitter_id,
                f"Suggestion {sug['suggestion_id']} acknowledged",
                f"Your suggestion has been acknowledged. **+₱{rate}** added to your earnings.",
            )
            await submitter.send(embed=dm)
        except discord.HTTPException:
            pass
        await interaction.response.send_message(embed=embeds.success_embed(f"{sug['suggestion_id']} acknowledged and credited."), ephemeral=True)

    @suggestion.command(name="dismiss", description="Dismiss a suggestion")
    @app_commands.describe(suggestion_id="Suggestion ID")
    async def suggestion_dismiss(self, interaction: discord.Interaction, suggestion_id: str) -> None:
        if not await is_owner(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Only the bot owner can use this."),
                ephemeral=True,
            )
            return
        sug = await db.get_suggestion(suggestion_id)
        if not sug or sug.get("status") not in {"submitted", "acknowledged"}:
            await interaction.response.send_message(
                embed=embeds.error_embed("Suggestion not found or not pending."),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(SuggestionDismissModalImpl(self, sug["suggestion_id"]))

    async def process_dismiss(
        self, interaction: discord.Interaction, suggestion_id: str, reason: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        sug = await db.get_suggestion(suggestion_id)
        if not sug:
            await interaction.followup.send(embed=embeds.error_embed("Not found."), ephemeral=True)
            return
        await db.update_suggestion_status(
            suggestion_id, "dismissed", dismiss_reason=reason or None, actioned_at=now_pht()
        )
        sch = await config.get_channel(self.bot, "channel_suggestions")
        if sch and sug.get("message_id"):
            try:
                m = await sch.fetch_message(int(sug["message_id"]))
                s2 = await db.get_suggestion(suggestion_id)
                u = await self.bot.fetch_user(int(s2["submitter_id"]))
                await m.edit(embed=embeds.suggestion_embed(s2, u))
            except discord.HTTPException:
                pass
        try:
            u = await self.bot.fetch_user(int(sug["submitter_id"]))
            r = reason.strip() if reason else "No reason provided"
            await u.send(
                f"Your suggestion {suggestion_id} has been dismissed. Reason: {r}."
            )
        except discord.HTTPException:
            pass
        await log_event(
            self.bot,
            "SUGGESTION_DISMISS",
            {"suggestion_id": suggestion_id, "by": str(interaction.user.id)},
        )
        await interaction.followup.send(embed=embeds.success_embed("Dismissed."), ephemeral=True)

    @suggestion.command(name="list", description="List suggestions")
    @app_commands.describe(status="Filter")
    @app_commands.choices(
        status=[
            app_commands.Choice(name="submitted", value="submitted"),
            app_commands.Choice(name="acknowledged", value="acknowledged"),
            app_commands.Choice(name="implemented", value="implemented"),
            app_commands.Choice(name="dismissed", value="dismissed"),
            app_commands.Choice(name="all", value="all"),
        ]
    )
    async def suggestion_list(
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
        rows = await db.get_suggestions_by_status(status)
        if not rows:
            await interaction.response.send_message(embed=embeds.error_embed("None found."), ephemeral=True)
            return
        lines: list[str] = []
        for s in rows:
            t = await db.get_tester(s["submitter_id"])
            dn = t.get("display_name", "?") if t else "?"
            lines.append(
                f"**{s['suggestion_id']}** — {s['title'][:60]} — {s['feature_tag']} — {dn} — {s['submitted_at']}"
            )
        chunk = 5
        pages: list[discord.Embed] = []
        total_pages = max(1, (len(lines) + chunk - 1) // chunk)
        for i in range(0, len(lines), chunk):
            e = discord.Embed(
                title=f"Suggestions ({status})",
                description="\n".join(lines[i : i + chunk]),
                color=embeds.EMBED_COLOR,
            )
            e.set_footer(text=f"Page {len(pages) + 1}/{total_pages}")
            pages.append(e)
        view = PaginationView(author_id=interaction.user.id, pages=pages)
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)
        msg = await interaction.original_response()
        view.message = msg

    @suggestion.command(name="info", description="Suggestion details")
    @app_commands.describe(suggestion_id="Suggestion ID")
    async def suggestion_info(self, interaction: discord.Interaction, suggestion_id: str) -> None:
        if not await is_active_tester(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("You need to register first."),
                ephemeral=True,
            )
            return
        s = await db.get_suggestion(suggestion_id)
        if not s:
            await interaction.response.send_message(
                embed=embeds.error_embed("Not found."),
                ephemeral=True,
            )
            return
        u = await self.bot.fetch_user(int(s["submitter_id"]))
        await interaction.response.send_message(embed=embeds.suggestion_embed(s, u), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Suggestions(bot))


from __future__ import annotations

import asyncio
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from database import db
from database.db import DEFAULT_CONFIG
from ui import embeds
from ui.modals import (
    ExistingChannelsModal,
    ExistingRolesModal,
    FeaturesEditModal,
    MilestoneModal,
    RatesSetupModal,
)
from utils import config
from utils.checks import is_owner
from utils.parsing import parse_rates_block, parse_snowflake

setup_sessions: dict[int, dict[str, Any]] = {}


def _session(uid: int) -> dict[str, Any]:
    if uid not in setup_sessions:
        setup_sessions[uid] = {
            "step": 1,
            "roles": {},
            "channels": {},
            "rates": dict(DEFAULT_CONFIG),
            "features": [],
            "milestones": [],
        }
    return setup_sessions[uid]


async def _safe_send_log(bot, embed: discord.Embed) -> None:
    ch = await config.get_channel(bot, "channel_bot_logs")
    if ch:
        try:
            await ch.send(embed=embed)
        except discord.HTTPException:
            pass


class Setup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_unload(self) -> None:
        setup_sessions.clear()

    @app_commands.command(name="setup", description="Run the UAT setup wizard (owner only)")
    async def setup_cmd(self, interaction: discord.Interaction) -> None:
        if not await is_owner(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Only the bot owner can run setup."),
                ephemeral=True,
            )
            return
        if await db.get_config("setup_complete") == "true":
            await interaction.response.send_message(
                embed=embeds.error_embed(
                    "Setup has already been completed. Use `/config set` to change individual settings."
                ),
                ephemeral=True,
            )
            return
        if not interaction.guild:
            await interaction.response.send_message(
                embed=embeds.error_embed("Use this in a server."),
                ephemeral=True,
            )
            return
        uid = interaction.user.id
        setup_sessions.pop(uid, None)
        _session(uid)["step"] = 1
        await interaction.response.send_message(
            embed=embeds.confirmation_embed(
                "Step 1 — Roles",
                "Should I **create** UAT roles, or **map** existing roles?",
            ),
            view=RoleStepView(self),
            ephemeral=True,
        )

    @app_commands.command(name="setup_reset", description="Wipe bot data and re-run setup (owner only)")
    async def setup_reset(self, interaction: discord.Interaction) -> None:
        if not await is_owner(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Only the bot owner can reset setup."),
                ephemeral=True,
            )
            return
        view = discord.ui.View(timeout=60)

        async def confirm(i: discord.Interaction) -> None:
            if i.user.id != interaction.user.id:
                await i.response.send_message("Not for you.", ephemeral=True)
                return
            await i.response.defer(ephemeral=True)
            await db.reset_db()
            setup_sessions.pop(interaction.user.id, None)
            await i.followup.send(
                embed=embeds.success_embed("Database reset. Run /setup again."),
                ephemeral=True,
            )

        async def cancel(i: discord.Interaction) -> None:
            if i.user.id != interaction.user.id:
                await i.response.send_message("Not for you.", ephemeral=True)
                return
            await i.response.send_message("Cancelled.", ephemeral=True)

        b1 = discord.ui.Button(label="Confirm Reset", style=discord.ButtonStyle.danger)
        b2 = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        b1.callback = confirm
        b2.callback = cancel
        view.add_item(b1)
        view.add_item(b2)
        await interaction.response.send_message(
            embed=embeds.confirmation_embed(
                "Confirm reset",
                "This will **delete all bot data** and re-seed the database. Continue?",
            ),
            view=view,
            ephemeral=True,
        )

    async def create_roles(self, guild: discord.Guild, uid: int) -> None:
        admin = await guild.create_role(name="UAT Admin", color=discord.Color.gold())
        tester = await guild.create_role(name="Tester", color=discord.Color.green())
        senior = await guild.create_role(name="Senior Tester", color=discord.Color.blue())
        sess = _session(uid)
        sess["roles"] = {
            "role_admin": str(admin.id),
            "role_tester": str(tester.id),
            "role_senior_tester": str(senior.id),
        }
        for k, v in sess["roles"].items():
            await db.set_config(k, v)

    async def prompt_existing_roles(self, interaction: discord.Interaction, uid: int) -> None:
        await interaction.response.send_modal(ExistingRolesModalImpl(self, uid))

    async def create_channels(self, guild: discord.Guild, uid: int) -> None:
        sess = _session(uid)
        admin_id = int(sess["roles"]["role_admin"])
        tester_id = int(sess["roles"]["role_tester"])
        everyone = guild.default_role
        admin_role = guild.get_role(admin_id)
        tester_role = guild.get_role(tester_id)
        cat = await guild.create_category("📋 UAT Testing")
        over_bot_logs = {
            everyone: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        if admin_role:
            over_bot_logs[admin_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True
            )
        over_guidelines = {
            everyone: discord.PermissionOverwrite(view_channel=False),
        }
        if tester_role:
            over_guidelines[tester_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=False
            )
        if admin_role:
            over_guidelines[admin_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True
            )
        over_guidelines[guild.me] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True
        )

        names = [
            ("uat-announcements", {}),
            ("register-here", {}),
            ("bug-reports", {}),
            ("suggestions", {}),
            ("payout-log", {}),
            ("bot-logs", over_bot_logs),
            ("tester-guidelines", over_guidelines),
        ]
        keys = [
            "channel_announcements",
            "channel_register_here",
            "channel_bug_reports",
            "channel_suggestions",
            "channel_payout_log",
            "channel_bot_logs",
            "channel_guidelines",
        ]
        mapping: dict[str, str] = {}
        for (name, ow), key in zip(names, keys):
            ch = await guild.create_text_channel(name, category=cat, overwrites=ow or None)
            mapping[key] = str(ch.id)
            await asyncio.sleep(0.3)
        sess["channels"] = mapping
        for k, v in mapping.items():
            await db.set_config(k, v)

    async def prompt_existing_channels(self, interaction: discord.Interaction, uid: int) -> None:
        await interaction.response.send_modal(ExistingChannelsModalImpl(self, uid))

    async def step3_rates(self, interaction: discord.Interaction, uid: int) -> None:
        await interaction.response.send_message(
            embed=embeds.confirmation_embed(
                "Step 3 — Rates",
                "Default rates are shown in the next modal placeholder. Click **Edit rates**.",
            ),
            view=RatesStepView(self, uid),
            ephemeral=True,
        )

    async def step4_features(self, interaction: discord.Interaction, uid: int) -> None:
        await interaction.response.send_message(
            embed=embeds.confirmation_embed("Step 4 — Features", "Edit the feature list for `/suggest`."),
            view=FeaturesStepView(self, uid),
            ephemeral=True,
        )

    async def step5_milestones(self, interaction: discord.Interaction, uid: int) -> None:
        await interaction.response.send_message(
            embed=embeds.confirmation_embed(
                "Step 5 — Milestones",
                "Add a milestone now or skip.",
            ),
            view=MilestoneStepView(self, uid),
            ephemeral=True,
        )

    async def build_summary_embed(self, uid: int) -> discord.Embed:
        sess = _session(uid)
        rate_keys = [
            "bug_report_rate",
            "bug_resolve_bonus",
            "suggestion_submit_rate",
            "suggestion_implement_bonus",
            "weekly_cap",
            "daily_bug_limit",
            "daily_suggestion_limit",
        ]
        payload = {
            "Roles": sess.get("roles", {}),
            "Channels": sess.get("channels", {}),
            "Rates": {k: sess["rates"].get(k) for k in rate_keys},
            "Features": sess.get("features") or await config.get_feature_list(),
        }
        return embeds.setup_summary_embed(payload)

    async def send_step6_followup(self, interaction: discord.Interaction, uid: int) -> None:
        emb = await self.build_summary_embed(uid)
        await interaction.followup.send(
            embed=emb,
            view=ConfirmSetupView(self, uid),
            ephemeral=True,
        )

    async def finalize_setup(self, interaction: discord.Interaction, uid: int) -> None:
        await db.set_config("setup_complete", "true")
        guide = await config.get_channel(self.bot, "channel_guidelines")
        if guide:
            cfg = await db.get_all_config()
            rates = {
                "bug_report_rate": cfg.get("bug_report_rate", "?"),
                "bug_resolve_bonus": cfg.get("bug_resolve_bonus", "?"),
                "suggestion_submit_rate": cfg.get("suggestion_submit_rate", "?"),
                "suggestion_implement_bonus": cfg.get("suggestion_implement_bonus", "?"),
                "weekly_cap": cfg.get("weekly_cap", "?"),
            }
            msg = await guide.send(embed=embeds.tester_guidelines_embed(rates))
            try:
                await msg.pin()
            except discord.HTTPException:
                pass
        setup_sessions.pop(uid, None)
        await interaction.response.send_message(
            embed=embeds.success_embed("Setup complete! Guidelines posted and pinned."),
            ephemeral=True,
        )
        await _safe_send_log(
            self.bot,
            embeds.bot_log_embed("SETUP_COMPLETE", {"by": str(uid)}),
        )


class RoleStepView(discord.ui.View):
    def __init__(self, cog: Setup):
        super().__init__(timeout=300)
        self.cog = cog

    @discord.ui.button(label="Create New", style=discord.ButtonStyle.success)
    async def create_new(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not interaction.guild:
            return
        uid = interaction.user.id
        await self.cog.create_roles(interaction.guild, uid)
        await interaction.response.edit_message(
            content="Roles created.",
            embed=None,
            view=None,
        )
        await interaction.followup.send(
            embed=embeds.confirmation_embed("Step 2 — Channels", "Create channels or map existing?"),
            view=ChannelStepView(self.cog),
            ephemeral=True,
        )

    @discord.ui.button(label="Use Existing", style=discord.ButtonStyle.secondary)
    async def use_existing(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.cog.prompt_existing_roles(interaction, interaction.user.id)


class ExistingRolesModalImpl(ExistingRolesModal):
    def __init__(self, cog: Setup, uid: int):
        super().__init__()
        self.cog = cog
        self.uid = uid

    async def on_submit(self, interaction: discord.Interaction) -> None:
        ga = parse_snowflake(str(self.admin_role.value))
        gt = parse_snowflake(str(self.tester_role.value))
        gs = parse_snowflake(str(self.senior_role.value))
        if not ga or not gt or not gs:
            await interaction.response.send_message(
                embed=embeds.error_embed("Could not parse role IDs."),
                ephemeral=True,
            )
            return
        sess = _session(self.uid)
        sess["roles"] = {
            "role_admin": str(ga),
            "role_tester": str(gt),
            "role_senior_tester": str(gs),
        }
        for k, v in sess["roles"].items():
            await db.set_config(k, v)
        await interaction.response.send_message(
            embed=embeds.success_embed("Roles saved."),
            ephemeral=True,
        )
        await interaction.followup.send(
            embed=embeds.confirmation_embed("Step 2 — Channels", "Create channels or map existing?"),
            view=ChannelStepView(self.cog),
            ephemeral=True,
        )


class ChannelStepView(discord.ui.View):
    def __init__(self, cog: Setup):
        super().__init__(timeout=300)
        self.cog = cog

    @discord.ui.button(label="Create New", style=discord.ButtonStyle.success)
    async def create_new(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not interaction.guild:
            return
        uid = interaction.user.id
        await interaction.response.defer(ephemeral=True)
        await self.cog.create_channels(interaction.guild, uid)
        await interaction.followup.send(embed=embeds.success_embed("Channels created."), ephemeral=True)
        await interaction.followup.send(
            embed=embeds.confirmation_embed(
                "Step 3 — Rates",
                "Click **Edit rates** to open the modal (defaults in placeholder).",
            ),
            view=RatesStepView(self.cog, uid),
            ephemeral=True,
        )

    @discord.ui.button(label="Use Existing", style=discord.ButtonStyle.secondary)
    async def use_existing(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.cog.prompt_existing_channels(interaction, interaction.user.id)


class ExistingChannelsModalImpl(ExistingChannelsModal):
    def __init__(self, cog: Setup, uid: int):
        super().__init__()
        self.cog = cog
        self.uid = uid

    async def on_submit(self, interaction: discord.Interaction) -> None:
        lines = [ln.strip() for ln in str(self.mapping.value).splitlines() if ln.strip()]
        keys = [
            "channel_announcements",
            "channel_register_here",
            "channel_bug_reports",
            "channel_suggestions",
            "channel_payout_log",
            "channel_bot_logs",
            "channel_guidelines",
        ]
        if len(lines) < 7:
            await interaction.response.send_message(
                embed=embeds.error_embed("Provide exactly 7 channel IDs (one per line)."),
                ephemeral=True,
            )
            return
        mapping: dict[str, str] = {}
        for k, ln in zip(keys, lines[:7]):
            sid = parse_snowflake(ln)
            if not sid:
                await interaction.response.send_message(
                    embed=embeds.error_embed(f"Could not parse channel ID: {ln}"),
                    ephemeral=True,
                )
                return
            mapping[k] = str(sid)
        sess = _session(self.uid)
        sess["channels"] = mapping
        for kk, vv in mapping.items():
            await db.set_config(kk, vv)
        await interaction.response.send_message(embed=embeds.success_embed("Channels saved."), ephemeral=True)
        await interaction.followup.send(
            embed=embeds.confirmation_embed(
                "Step 3 — Rates",
                "Click **Edit rates** to open the modal.",
            ),
            view=RatesStepView(self.cog, self.uid),
            ephemeral=True,
        )


class RatesSetupModalImpl(RatesSetupModal):
    def __init__(self, cog: Setup, uid: int):
        super().__init__()
        self.cog = cog
        self.uid = uid

    async def on_submit(self, interaction: discord.Interaction) -> None:
        parsed = parse_rates_block(str(self.rates_text.value))
        if not parsed:
            await interaction.response.send_message(
                embed=embeds.error_embed(
                    "Invalid rates. Use lines like `bug_report_rate: 15` for all 7 keys."
                ),
                ephemeral=True,
            )
            return
        sess = _session(self.uid)
        for k, v in parsed.items():
            sess["rates"][k] = str(v)
            await db.set_config(k, str(v))
        await interaction.response.send_message(embed=embeds.success_embed("Rates saved."), ephemeral=True)
        await interaction.followup.send(
            embed=embeds.confirmation_embed("Step 4 — Features", "Edit the feature list."),
            view=FeaturesStepView(self.cog, self.uid),
            ephemeral=True,
        )


class RatesStepView(discord.ui.View):
    def __init__(self, cog: Setup, uid: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.uid = uid

    @discord.ui.button(label="Edit rates", style=discord.ButtonStyle.primary)
    async def edit(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(RatesSetupModalImpl(self.cog, self.uid))

    @discord.ui.button(label="Use defaults", style=discord.ButtonStyle.secondary)
    async def skip(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        sess = _session(self.uid)
        rate_keys = [
            "bug_report_rate",
            "bug_resolve_bonus",
            "suggestion_submit_rate",
            "suggestion_implement_bonus",
            "weekly_cap",
            "daily_bug_limit",
            "daily_suggestion_limit",
        ]
        for k in rate_keys:
            v = sess["rates"].get(k, DEFAULT_CONFIG[k])
            await db.set_config(k, str(v))
        await interaction.response.send_message(
            embed=embeds.success_embed("Using default rates from session."),
            ephemeral=True,
        )
        await interaction.followup.send(
            embed=embeds.confirmation_embed("Step 4 — Features", "Edit the feature list."),
            view=FeaturesStepView(self.cog, self.uid),
            ephemeral=True,
        )


class FeaturesEditModalImpl(FeaturesEditModal):
    def __init__(self, cog: Setup, uid: int):
        super().__init__()
        self.cog = cog
        self.uid = uid

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = str(self.features.value)
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if not any(l.lower() == "other" for l in lines):
            lines.append("Other")
        text = "\n".join(lines)
        await db.set_config("feature_list", text)
        sess = _session(self.uid)
        sess["features"] = lines
        await interaction.response.send_message(embed=embeds.success_embed("Features saved."), ephemeral=True)
        await interaction.followup.send(
            embed=embeds.confirmation_embed("Step 5 — Milestones", "Add a milestone or skip."),
            view=MilestoneStepView(self.cog, self.uid),
            ephemeral=True,
        )


class FeaturesStepView(discord.ui.View):
    def __init__(self, cog: Setup, uid: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.uid = uid

    @discord.ui.button(label="Edit features", style=discord.ButtonStyle.primary)
    async def edit(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(FeaturesEditModalImpl(self.cog, self.uid))

    @discord.ui.button(label="Use defaults", style=discord.ButtonStyle.secondary)
    async def skip(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        feats = await config.get_feature_list()
        _session(self.uid)["features"] = feats
        await interaction.response.send_message(
            embed=embeds.success_embed("Using default feature list."),
            ephemeral=True,
        )
        await interaction.followup.send(
            embed=embeds.confirmation_embed("Step 5 — Milestones", "Add a milestone or skip."),
            view=MilestoneStepView(self.cog, self.uid),
            ephemeral=True,
        )


class MilestoneModalImpl(MilestoneModal):
    def __init__(self, cog: Setup, uid: int):
        super().__init__()
        self.cog = cog
        self.uid = uid

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await db.create_milestone(
            str(self.name.value),
            str(self.description.value),
            str(self.rate_changes.value),
        )
        sess = _session(self.uid)
        sess["milestones"].append(str(self.name.value))
        await interaction.response.send_message(embed=embeds.success_embed("Milestone saved."), ephemeral=True)
        await interaction.followup.send(
            "Add another milestone?",
            view=MilestoneAgainView(self.cog, self.uid),
            ephemeral=True,
        )


class MilestoneStepView(discord.ui.View):
    def __init__(self, cog: Setup, uid: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.uid = uid

    @discord.ui.button(label="Add milestone", style=discord.ButtonStyle.success)
    async def add(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(MilestoneModalImpl(self.cog, self.uid))

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary)
    async def skip(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        uid = interaction.user.id
        await interaction.response.edit_message(content="Skipping milestones.", embed=None, view=None)
        await self.cog.send_step6_followup(interaction, uid)


class MilestoneAgainView(discord.ui.View):
    def __init__(self, cog: Setup, uid: int):
        super().__init__(timeout=120)
        self.cog = cog
        self.uid = uid

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(MilestoneModalImpl(self.cog, self.uid))

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Done with milestones.", view=None)
        await self.cog.send_step6_followup(interaction, self.uid)


class ConfirmSetupView(discord.ui.View):
    def __init__(self, cog: Setup, uid: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.uid = uid

    @discord.ui.button(label="Confirm Setup", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.cog.finalize_setup(interaction, self.uid)

    @discord.ui.button(label="Start Over", style=discord.ButtonStyle.danger, emoji="🔄")
    async def restart(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        uid = interaction.user.id
        setup_sessions.pop(uid, None)
        _session(uid)["step"] = 1
        await interaction.response.edit_message(content="Restarting setup…", embed=None, view=None)
        await interaction.followup.send(
            embed=embeds.confirmation_embed(
                "Step 1 — Roles",
                "Should I **create** UAT roles, or **map** existing roles?",
            ),
            view=RoleStepView(self.cog),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Setup(bot))

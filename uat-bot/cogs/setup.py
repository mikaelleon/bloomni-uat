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
    FeaturesEditModal,
    MilestoneModal,
    RatesSetupModal,
)
from utils import config
from utils.checks import is_owner
from utils.parsing import parse_rates_block
from utils.logging import log_event

setup_sessions: dict[int, dict[str, Any]] = {}
ROLE_SEQUENCE = [
    ("role_admin", "UAT Admin role"),
    ("role_tester", "Tester role"),
    ("role_senior_tester", "Senior Tester role"),
]
CHANNEL_SEQUENCE = [
    ("channel_announcements", "uat-announcements"),
    ("channel_register_here", "register-here"),
    ("channel_bug_reports", "bug-reports"),
    ("channel_suggestions", "suggestions"),
    ("channel_payout_log", "payout-log"),
    ("channel_bot_logs", "bot-logs"),
    ("channel_guidelines", "tester-guidelines"),
]


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


async def _safe_send_log(bot, action: str, details: dict[str, Any]) -> None:
    await log_event(bot, action, details)


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
        await interaction.response.send_message(
            embed=embeds.confirmation_embed(
                "Map Existing Roles",
                "Select the role for **UAT Admin**.",
            ),
            view=ExistingRoleSelectView(self, uid, 0, {}),
            ephemeral=True,
        )

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
            ("uat-announcements", None),
            ("register-here", None),
            ("bug-reports", None),
            ("suggestions", None),
            ("payout-log", None),
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
            if ow is None:
                ch = await guild.create_text_channel(name, category=cat)
            else:
                ch = await guild.create_text_channel(
                    name, category=cat, overwrites=ow
                )
            mapping[key] = str(ch.id)
            await asyncio.sleep(0.3)
        sess["channels"] = mapping
        for k, v in mapping.items():
            await db.set_config(k, v)

    async def prompt_existing_channels(self, interaction: discord.Interaction, uid: int) -> None:
        await interaction.response.send_message(
            embed=embeds.confirmation_embed(
                "Map Existing Channels",
                "Select the channel for **uat-announcements**.",
            ),
            view=ExistingChannelSelectView(self, uid, 0, {}),
            ephemeral=True,
        )

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

    async def build_summary_pages(self, uid: int) -> list[discord.Embed]:
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
        pages: list[discord.Embed] = []
        sections = [
            ("Roles", sess.get("roles", {})),
            ("Channels", sess.get("channels", {})),
            ("Rates", {k: sess["rates"].get(k) for k in rate_keys}),
            ("Features", sess.get("features") or await config.get_feature_list()),
            ("Milestones", sess.get("milestones") or ["None configured"]),
        ]
        total = len(sections)
        for i, (name, value) in enumerate(sections, start=1):
            emb = discord.Embed(
                title=f"Setup summary ({i}/{total})",
                description=f"Review **{name}** before confirming setup.",
                color=embeds.EMBED_COLOR,
            )
            rendered = str(value) if not isinstance(value, list) else "\n".join(value)
            emb.add_field(name=name, value=rendered[:1024] or "—", inline=False)
            pages.append(emb)
        return pages

    async def send_step6_followup(self, interaction: discord.Interaction, uid: int) -> None:
        pages = await self.build_summary_pages(uid)
        await interaction.followup.send(
            embed=pages[0],
            view=ConfirmSetupView(self, uid, pages),
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
        await _safe_send_log(self.bot, "SETUP_COMPLETE", {"by": str(uid)})

    async def cancel_setup(self, interaction: discord.Interaction, uid: int) -> None:
        setup_sessions.pop(uid, None)
        await interaction.response.edit_message(
            embed=embeds.warning_embed("Setup cancelled.", "Run /setup when ready."),
            view=None,
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

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary)
    async def skip_step(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        # Skip by creating default roles so setup can continue safely.
        if not interaction.guild:
            return
        uid = interaction.user.id
        await self.cog.create_roles(interaction.guild, uid)
        await interaction.response.edit_message(
            embed=embeds.warning_embed(
                "Roles step skipped.",
                "Default UAT roles were created automatically.",
            ),
            view=None,
        )
        await interaction.followup.send(
            embed=embeds.confirmation_embed("Step 2 — Channels", "Create channels or map existing?"),
            view=ChannelStepView(self.cog),
            ephemeral=True,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_step(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.cog.cancel_setup(interaction, interaction.user.id)


class ExistingRoleSelect(discord.ui.RoleSelect):
    def __init__(self, parent: "ExistingRoleSelectView"):
        key, label = ROLE_SEQUENCE[parent.index]
        super().__init__(
            placeholder=f"Select {label}",
            min_values=1,
            max_values=1,
        )
        self.parent_view = parent
        self.key = key

    async def callback(self, interaction: discord.Interaction) -> None:
        self.parent_view.mapping[self.key] = str(self.values[0].id)
        next_index = self.parent_view.index + 1
        if next_index < len(ROLE_SEQUENCE):
            _, next_label = ROLE_SEQUENCE[next_index]
            await interaction.response.edit_message(
                embed=embeds.confirmation_embed(
                    "Map Existing Roles",
                    f"Saved. Now select **{next_label}**.",
                ),
                view=ExistingRoleSelectView(
                    self.parent_view.cog,
                    self.parent_view.uid,
                    next_index,
                    self.parent_view.mapping,
                ),
            )
            return
        sess = _session(self.parent_view.uid)
        sess["roles"] = dict(self.parent_view.mapping)
        for k, v in sess["roles"].items():
            await db.set_config(k, v)
        await interaction.response.edit_message(embed=embeds.success_embed("Roles saved."), view=None)
        await interaction.followup.send(
            embed=embeds.confirmation_embed("Step 2 — Channels", "Create channels or map existing?"),
            view=ChannelStepView(self.parent_view.cog),
            ephemeral=True,
        )


class ExistingRoleSelectView(discord.ui.View):
    def __init__(self, cog: Setup, uid: int, index: int, mapping: dict[str, str]):
        super().__init__(timeout=180)
        self.cog = cog
        self.uid = uid
        self.index = index
        self.mapping = mapping
        self.add_item(ExistingRoleSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.uid:
            await interaction.response.send_message("Only the setup owner can use this.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.index == 0:
            await interaction.response.edit_message(
                embed=embeds.confirmation_embed(
                    "Step 1 — Roles",
                    "Should I **create** UAT roles, or **map** existing roles?",
                ),
                view=RoleStepView(self.cog),
            )
            return
        prev_index = self.index - 1
        _, prev_label = ROLE_SEQUENCE[prev_index]
        await interaction.response.edit_message(
            embed=embeds.confirmation_embed(
                "Map Existing Roles",
                f"Go back: select **{prev_label}**.",
            ),
            view=ExistingRoleSelectView(self.cog, self.uid, prev_index, self.mapping),
        )

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        key, _ = ROLE_SEQUENCE[self.index]
        if key not in self.mapping:
            await interaction.response.send_message(
                embed=embeds.warning_embed("Please select a role first."),
                ephemeral=True,
            )
            return
        next_index = self.index + 1
        if next_index < len(ROLE_SEQUENCE):
            _, next_label = ROLE_SEQUENCE[next_index]
            await interaction.response.edit_message(
                embed=embeds.confirmation_embed(
                    "Map Existing Roles",
                    f"Now select **{next_label}**.",
                ),
                view=ExistingRoleSelectView(self.cog, self.uid, next_index, self.mapping),
            )
            return
        sess = _session(self.uid)
        sess["roles"] = dict(self.mapping)
        for k, v in sess["roles"].items():
            await db.set_config(k, v)
        await interaction.response.edit_message(embed=embeds.success_embed("Roles saved."), view=None)
        await interaction.followup.send(
            embed=embeds.confirmation_embed("Step 2 — Channels", "Create channels or map existing?"),
            view=ChannelStepView(self.cog),
            ephemeral=True,
        )

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.guild:
            return
        await self.cog.create_roles(interaction.guild, self.uid)
        await interaction.response.edit_message(
            embed=embeds.warning_embed("Role mapping skipped.", "Default roles were created."),
            view=None,
        )
        await interaction.followup.send(
            embed=embeds.confirmation_embed("Step 2 — Channels", "Create channels or map existing?"),
            view=ChannelStepView(self.cog),
            ephemeral=True,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cog.cancel_setup(interaction, self.uid)


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

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary)
    async def skip_step(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not interaction.guild:
            return
        uid = interaction.user.id
        await interaction.response.defer(ephemeral=True)
        await self.cog.create_channels(interaction.guild, uid)
        await interaction.followup.send(
            embed=embeds.warning_embed("Channel mapping skipped.", "Default channels were created."),
            ephemeral=True,
        )
        await interaction.followup.send(
            embed=embeds.confirmation_embed(
                "Step 3 — Rates",
                "Click **Edit rates** to open the modal (defaults in placeholder).",
            ),
            view=RatesStepView(self.cog, uid),
            ephemeral=True,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_step(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.cog.cancel_setup(interaction, interaction.user.id)


class ExistingChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, parent: "ExistingChannelSelectView"):
        _, label = CHANNEL_SEQUENCE[parent.index]
        super().__init__(
            placeholder=f"Select #{label}",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
        )
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        key, _ = CHANNEL_SEQUENCE[self.parent_view.index]
        self.parent_view.mapping[key] = str(self.values[0].id)
        next_index = self.parent_view.index + 1
        if next_index < len(CHANNEL_SEQUENCE):
            _, next_label = CHANNEL_SEQUENCE[next_index]
            await interaction.response.edit_message(
                embed=embeds.confirmation_embed(
                    "Map Existing Channels",
                    f"Saved. Now select **{next_label}**.",
                ),
                view=ExistingChannelSelectView(
                    self.parent_view.cog,
                    self.parent_view.uid,
                    next_index,
                    self.parent_view.mapping,
                ),
            )
            return
        sess = _session(self.parent_view.uid)
        sess["channels"] = dict(self.parent_view.mapping)
        for kk, vv in sess["channels"].items():
            await db.set_config(kk, vv)
        await interaction.response.edit_message(embed=embeds.success_embed("Channels saved."), view=None)
        await interaction.followup.send(
            embed=embeds.confirmation_embed(
                "Step 3 — Rates",
                "Click **Edit rates** to open the modal.",
            ),
            view=RatesStepView(self.parent_view.cog, self.parent_view.uid),
            ephemeral=True,
        )


class ExistingChannelSelectView(discord.ui.View):
    def __init__(self, cog: Setup, uid: int, index: int, mapping: dict[str, str]):
        super().__init__(timeout=180)
        self.cog = cog
        self.uid = uid
        self.index = index
        self.mapping = mapping
        self.add_item(ExistingChannelSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.uid:
            await interaction.response.send_message("Only the setup owner can use this.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.index == 0:
            await interaction.response.edit_message(
                embed=embeds.confirmation_embed("Step 2 — Channels", "Create channels or map existing?"),
                view=ChannelStepView(self.cog),
            )
            return
        prev_index = self.index - 1
        _, prev_label = CHANNEL_SEQUENCE[prev_index]
        await interaction.response.edit_message(
            embed=embeds.confirmation_embed(
                "Map Existing Channels",
                f"Go back: select **{prev_label}**.",
            ),
            view=ExistingChannelSelectView(self.cog, self.uid, prev_index, self.mapping),
        )

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        key, _ = CHANNEL_SEQUENCE[self.index]
        if key not in self.mapping:
            await interaction.response.send_message(
                embed=embeds.warning_embed("Please select a channel first."),
                ephemeral=True,
            )
            return
        next_index = self.index + 1
        if next_index < len(CHANNEL_SEQUENCE):
            _, next_label = CHANNEL_SEQUENCE[next_index]
            await interaction.response.edit_message(
                embed=embeds.confirmation_embed(
                    "Map Existing Channels",
                    f"Now select **{next_label}**.",
                ),
                view=ExistingChannelSelectView(self.cog, self.uid, next_index, self.mapping),
            )
            return
        sess = _session(self.uid)
        sess["channels"] = dict(self.mapping)
        for kk, vv in sess["channels"].items():
            await db.set_config(kk, vv)
        await interaction.response.edit_message(embed=embeds.success_embed("Channels saved."), view=None)
        await interaction.followup.send(
            embed=embeds.confirmation_embed(
                "Step 3 — Rates",
                "Click **Edit rates** to open the modal.",
            ),
            view=RatesStepView(self.cog, self.uid),
            ephemeral=True,
        )

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer(ephemeral=True)
        await self.cog.create_channels(interaction.guild, self.uid)
        await interaction.followup.send(
            embed=embeds.warning_embed("Channel mapping skipped.", "Default channels were created."),
            ephemeral=True,
        )
        await interaction.followup.send(
            embed=embeds.confirmation_embed(
                "Step 3 — Rates",
                "Click **Edit rates** to open the modal.",
            ),
            view=RatesStepView(self.cog, self.uid),
            ephemeral=True,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cog.cancel_setup(interaction, self.uid)


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

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.cog.cancel_setup(interaction, self.uid)


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

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.cog.cancel_setup(interaction, self.uid)


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

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.cog.cancel_setup(interaction, self.uid)


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
    def __init__(self, cog: Setup, uid: int, pages: list[discord.Embed]):
        super().__init__(timeout=300)
        self.cog = cog
        self.uid = uid
        self.pages = pages
        self.index = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.uid:
            await interaction.response.send_message("Only the setup owner can use this.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=0)
    async def back(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.index = max(0, self.index - 1)
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, row=0)
    async def next(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.index = min(len(self.pages) - 1, self.index + 1)
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="Confirm Setup", style=discord.ButtonStyle.success, emoji="✅", row=1)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.cog.finalize_setup(interaction, self.uid)

    @discord.ui.button(label="Start Over", style=discord.ButtonStyle.danger, emoji="🔄", row=1)
    async def restart(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        uid = interaction.user.id
        setup_sessions.pop(uid, None)
        _session(uid)["step"] = 1
        await interaction.response.edit_message(content="Restarting setup...", embed=None, view=None)
        await interaction.followup.send(
            embed=embeds.confirmation_embed(
                "Step 1 — Roles",
                "Should I **create** UAT roles, or **map** existing roles?",
            ),
            view=RoleStepView(self.cog),
            ephemeral=True,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=1)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.cog.cancel_setup(interaction, self.uid)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Setup(bot))





from __future__ import annotations

import re

import discord
from discord import app_commands
from discord.ext import commands

from database import db
from ui import embeds
from ui.modals import RegistrationModal, UpdateGCashModal
from ui.views import PaginationView
from utils import config
from utils.checks import is_active_tester, is_admin, is_owner
from utils.crypto import encrypt_gcash, mask_gcash
from utils.time_utils import get_week_start, now_pht, today_pht
from utils.logging import log_event


GCASH_RE = re.compile(r"^09\d{9}$")


class RegistrationModalImpl(RegistrationModal):
    def __init__(self, cog: "Registration"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.process_registration(
            interaction, str(self.display_name.value), str(self.gcash_number.value)
        )


class UpdateGCashModalImpl(UpdateGCashModal):
    def __init__(self, cog: "Registration"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.process_update_gcash(interaction, str(self.gcash_number.value))


class TOSView(discord.ui.View):
    def __init__(self, cog: "Registration"):
        super().__init__(timeout=300)
        self.cog = cog

    @discord.ui.button(label="I Accept", style=discord.ButtonStyle.success, custom_id="tos_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(RegistrationModalImpl(self.cog))

    @discord.ui.button(label="I Decline", style=discord.ButtonStyle.danger, custom_id="tos_decline")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        for c in self.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True
        await interaction.response.edit_message(
            content="Registration cancelled. Come back when you're ready!",
            embed=None,
            view=self,
        )


class Registration(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="register", description="Register as a UAT tester")
    async def register(self, interaction: discord.Interaction) -> None:
        if await db.get_config("setup_complete") != "true":
            await interaction.response.send_message(
                embed=embeds.error_embed(
                    "The bot hasn't been set up yet. Ask the owner to run /setup first."
                ),
                ephemeral=True,
            )
            return
        reg_ch = await db.get_config("channel_register_here")
        if not reg_ch or str(interaction.channel_id) != reg_ch:
            await interaction.response.send_message(
                embed=embeds.error_embed("Please head to #register-here to register."),
                ephemeral=True,
            )
            return
        uid = str(interaction.user.id)
        if await db.get_tester(uid):
            await interaction.response.send_message(
                embed=embeds.error_embed(
                    "You're already registered. Use /update-gcash to change your GCash number."
                ),
                ephemeral=True,
            )
            return
        view = TOSView(self)
        await interaction.response.send_message(embed=embeds.tos_embed(), view=view, ephemeral=True)

    async def process_registration(
        self, interaction: discord.Interaction, display_name: str, gcash_raw: str
    ) -> None:
        if not GCASH_RE.match(gcash_raw.strip()):
            await interaction.response.send_message(
                embed=embeds.error_embed(
                    "Invalid GCash number. Use format 09XXXXXXXXX. Run /register again."
                ),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        enc = encrypt_gcash(gcash_raw.strip())
        await db.create_tester(uid, display_name, enc, now_pht())
        if interaction.guild:
            role = await config.get_role(interaction.guild, "role_tester")
            member = interaction.guild.get_member(interaction.user.id)
            if role and member:
                await member.add_roles(role, reason="UAT registration")
        ws = get_week_start(today_pht())
        await db.get_or_create_earnings(uid, ws)
        masked = mask_gcash(gcash_raw.strip())
        cfg = await db.get_all_config()
        rates = {
            "bug_report_rate": cfg.get("bug_report_rate", "0"),
            "bug_resolve_bonus": cfg.get("bug_resolve_bonus", "0"),
            "suggestion_submit_rate": cfg.get("suggestion_submit_rate", "0"),
            "suggestion_implement_bonus": cfg.get("suggestion_implement_bonus", "0"),
        }
        bug_ch = await config.get_channel(self.bot, "channel_bug_reports")
        sug_ch = await config.get_channel(self.bot, "channel_suggestions")
        guide_ch = await config.get_channel(self.bot, "channel_guidelines")
        channels = {
            "bug_reports": bug_ch.mention if bug_ch else "#bug-reports",
            "suggestions": sug_ch.mention if sug_ch else "#suggestions",
            "guidelines": guide_ch.mention if guide_ch else "#tester-guidelines",
        }
        try:
            await interaction.user.send(
                embed=embeds.registration_success_embed(display_name, masked, rates, channels)
            )
        except discord.HTTPException:
            pass
        await interaction.followup.send(
            embed=embeds.success_embed("You're registered! Check your DMs."),
            ephemeral=True,
        )
        await log_event(
            self.bot,
            "REGISTRATION",
            {
                "user_id": uid,
                "display_name": display_name,
                "timestamp": now_pht().isoformat(),
            },
        )

    @app_commands.command(name="update-gcash", description="Update your GCash number")
    async def update_gcash(self, interaction: discord.Interaction) -> None:
        if not await is_active_tester(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("You need to be an active tester to use this."),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(UpdateGCashModalImpl(self))

    async def process_update_gcash(self, interaction: discord.Interaction, gcash_raw: str) -> None:
        if not GCASH_RE.match(gcash_raw.strip()):
            await interaction.response.send_message(
                embed=embeds.error_embed("Invalid GCash number. Use format 09XXXXXXXXX."),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        enc = encrypt_gcash(gcash_raw.strip())
        await db.update_tester_gcash(uid, enc)
        masked = mask_gcash(gcash_raw.strip())
        try:
            await interaction.user.send(
                embed=embeds.success_embed(f"GCash updated. Masked number: {masked}")
            )
        except discord.HTTPException:
            pass
        await interaction.followup.send(
            embed=embeds.success_embed("GCash number updated. Check your DMs for confirmation."),
            ephemeral=True,
        )
        await log_event(
            self.bot,
            "GCASH_UPDATE",
            {"user_id": uid, "timestamp": now_pht().isoformat()},
        )

    tester = app_commands.Group(name="tester", description="Tester management")

    @tester.command(name="info", description="View tester profile")
    @app_commands.describe(user="User to inspect (admins only)")
    async def tester_info(self, interaction: discord.Interaction, user: discord.User | None = None) -> None:
        target = user or interaction.user
        if user is not None and user.id != interaction.user.id:
            if not await is_admin(interaction):
                await interaction.response.send_message(
                    embed=embeds.error_embed("Only admins can view other testers."),
                    ephemeral=True,
                )
                return
        else:
            if not await is_active_tester(interaction):
                await interaction.response.send_message(
                    embed=embeds.error_embed("You need to register first. Head to #register-here."),
                    ephemeral=True,
                )
                return
        uid = str(target.id)
        tester = await db.get_tester(uid)
        if not tester:
            await interaction.response.send_message(
                embed=embeds.error_embed("That user is not registered."),
                ephemeral=True,
            )
            return
        stats = await db.get_tester_all_time_stats(uid)
        await interaction.response.send_message(
            embed=embeds.tester_profile_embed(tester, stats),
            ephemeral=True,
        )

    @tester.command(name="list", description="List all testers")
    async def tester_list(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Only admins can use this."),
                ephemeral=True,
            )
            return
        testers = await db.get_all_testers(active_only=False)
        if not testers:
            await interaction.response.send_message(embed=embeds.error_embed("No testers."), ephemeral=True)
            return
        lines: list[str] = []
        for t in testers:
            uid = t["user_id"]
            try:
                u = await self.bot.fetch_user(int(uid))
                uname = str(u)
            except discord.HTTPException:
                uname = "unknown"
            act = "✅" if int(t.get("is_active", 0)) else "❌"
            lines.append(
                f"**{t.get('display_name', '?')}** — {uname} — {act} — weeks: {t.get('weeks_active', 0)}"
            )
        chunk = 5
        pages: list[discord.Embed] = []
        total_pages = (len(lines) + chunk - 1) // chunk
        for i in range(0, len(lines), chunk):
            part = lines[i : i + chunk]
            e = discord.Embed(
                title="Testers",
                description="\n".join(part),
                color=embeds.EMBED_COLOR,
            )
            e.set_footer(text=f"Page {len(pages) + 1}/{total_pages}")
            pages.append(e)
        view = PaginationView(author_id=interaction.user.id, pages=pages)
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)
        msg = await interaction.original_response()
        view.message = msg

    @tester.command(name="deactivate", description="Deactivate a tester")
    @app_commands.describe(user="Tester to deactivate")
    async def tester_deactivate(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if not await is_owner(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Only the bot owner can use this."),
                ephemeral=True,
            )
            return
        uid = str(user.id)
        t = await db.get_tester(uid)
        if not t or not int(t.get("is_active", 0)):
            await interaction.response.send_message(
                embed=embeds.error_embed("Tester not found or already inactive."),
                ephemeral=True,
            )
            return

        view = discord.ui.View(timeout=60)

        async def confirm(i: discord.Interaction) -> None:
            if i.user.id != interaction.user.id:
                await i.response.send_message("Not for you.", ephemeral=True)
                return
            await db.deactivate_tester(uid)
            if interaction.guild:
                role = await config.get_role(interaction.guild, "role_tester")
                if role and user:
                    await user.remove_roles(role, reason="Tester deactivated")
            try:
                await user.send(
                    "Your tester account has been deactivated. Contact the owner if you think this is a mistake."
                )
            except discord.HTTPException:
                pass
            await log_event(
                self.bot,
                "TESTER_DEACTIVATE",
                {"user_id": uid, "by": str(interaction.user.id)},
            )
            await i.response.edit_message(content="Tester deactivated.", embed=None, view=None)

        async def cancel(i: discord.Interaction) -> None:
            if i.user.id != interaction.user.id:
                await i.response.send_message("Not for you.", ephemeral=True)
                return
            await i.response.edit_message(content="Cancelled.", embed=None, view=None)

        b1 = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.success)
        b2 = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger)
        b1.callback = confirm
        b2.callback = cancel
        view.add_item(b1)
        view.add_item(b2)
        await interaction.response.send_message(
            embed=embeds.confirmation_embed(
                "Deactivate tester",
                f"Deactivate **{t.get('display_name', user.display_name)}**?",
            ),
            view=view,
            ephemeral=True,
        )

    @tester.command(name="reactivate", description="Reactivate a tester")
    @app_commands.describe(user="Tester to reactivate")
    async def tester_reactivate(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if not await is_owner(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Only the bot owner can use this."),
                ephemeral=True,
            )
            return
        uid = str(user.id)
        t = await db.get_tester(uid)
        if not t or int(t.get("is_active", 0)):
            await interaction.response.send_message(
                embed=embeds.error_embed("Tester not found or already active."),
                ephemeral=True,
            )
            return
        await db.reactivate_tester(uid)
        if interaction.guild:
            role = await config.get_role(interaction.guild, "role_tester")
            if role:
                await user.add_roles(role, reason="Tester reactivated")
        try:
            await user.send("Your tester account has been reactivated! Welcome back.")
        except discord.HTTPException:
            pass
        await log_event(
            self.bot,
            "TESTER_REACTIVATE",
            {"user_id": uid, "by": str(interaction.user.id)},
        )
        await interaction.response.send_message(
            embed=embeds.success_embed("Tester reactivated."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Registration(bot))







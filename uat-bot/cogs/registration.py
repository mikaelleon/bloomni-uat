from __future__ import annotations

import re
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from database import db
from ui import embeds
from ui.modals import (
    ApplicationRejectModal,
    RegistrationContextModal,
    RegistrationIdentityModal,
    UpdateGCashModal,
)
from ui.views import PaginationView
from utils import config
from utils.checks import is_active_tester, is_admin, is_owner
from utils.crypto import encrypt_gcash, mask_gcash
from utils.time_utils import get_week_start, now_pht, today_pht
from utils.logging import log_event


GCASH_RE = re.compile(r"^09\d{9}$")


class RegistrationIdentityModalImpl(RegistrationIdentityModal):
    def __init__(self, cog: "Registration"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.start_context_modal(
            interaction,
            {
                "display_name": str(self.display_name.value).strip(),
                "full_name": str(self.full_name.value).strip(),
                "gcash_number": str(self.gcash_number.value).strip(),
                "section_relationship": str(self.section_relationship.value).strip(),
            },
        )


class UpdateGCashModalImpl(UpdateGCashModal):
    def __init__(self, cog: "Registration"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.process_update_gcash(interaction, str(self.gcash_number.value))


class RegistrationContextModalImpl(RegistrationContextModal):
    def __init__(self, cog: "Registration", invite_code: str | None):
        super().__init__()
        self.cog = cog
        self.invite_code = invite_code

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.submit_application(
            interaction,
            {
                "hearing_source": str(self.hearing_source.value).strip(),
                "availability": str(self.availability.value or "").strip(),
                "device_platform": str(self.device_platform.value or "").strip(),
                "prior_experience": str(self.prior_experience.value or "").strip(),
                "tos_signature": str(self.tos_signature.value).strip(),
                "invite_code": self.invite_code or "",
            },
        )


class ApplicationRejectModalImpl(ApplicationRejectModal):
    def __init__(self, cog: "Registration", application_id: int):
        super().__init__()
        self.cog = cog
        self.application_id = application_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.reject_application(
            interaction, self.application_id, str(self.reason.value or "").strip()
        )


class CommitmentView(discord.ui.View):
    def __init__(self, cog: "Registration", invite_code: str | None):
        super().__init__(timeout=300)
        self.cog = cog
        self.invite_code = invite_code

    @discord.ui.button(
        label="I understand this is casual and pay is small",
        style=discord.ButtonStyle.primary,
    )
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(RegistrationIdentityModalImpl(self.cog))
        self.cog._invite_code_cache[str(interaction.user.id)] = self.invite_code or ""

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Registration cancelled.", embed=None, view=None)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ) -> None:
        await log_event(
            self.cog.bot,
            "REGISTRATION_COMMITMENT_VIEW_ERROR",
            {
                "user_id": str(getattr(interaction.user, "id", "unknown")),
                "item": str(getattr(item, "custom_id", getattr(item, "label", "unknown"))),
                "error": repr(error),
            },
            level="ERROR",
        )
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    embed=embeds.warning_embed(
                        "That interaction failed.",
                        "Please run /register again.",
                    ),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    embed=embeds.warning_embed(
                        "That interaction failed.",
                        "Please run /register again.",
                    ),
                    ephemeral=True,
                )
        except discord.HTTPException:
            pass


class ContextLaunchView(discord.ui.View):
    def __init__(self, cog: "Registration", user_id: int, invite_code: str | None):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        self.invite_code = invite_code

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your registration flow.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Continue to Step 2", style=discord.ButtonStyle.primary)
    async def continue_step2(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(RegistrationContextModalImpl(self.cog, self.invite_code))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            content="Registration cancelled.",
            embed=None,
            view=None,
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ) -> None:
        await log_event(
            self.cog.bot,
            "REGISTRATION_CONTEXT_LAUNCH_ERROR",
            {
                "user_id": str(getattr(interaction.user, "id", "unknown")),
                "item": str(getattr(item, "custom_id", getattr(item, "label", "unknown"))),
                "error": repr(error),
            },
            level="ERROR",
        )
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    embed=embeds.warning_embed(
                        "Could not open step 2 right now.",
                        "Please run /register again.",
                    ),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    embed=embeds.warning_embed(
                        "Could not open step 2 right now.",
                        "Please run /register again.",
                    ),
                    ephemeral=True,
                )
        except discord.HTTPException:
            pass


class TOSView(discord.ui.View):
    def __init__(self, cog: "Registration", invite_code: str | None):
        super().__init__(timeout=300)
        self.cog = cog
        self.invite_code = invite_code

    @discord.ui.button(label="I Accept", style=discord.ButtonStyle.success, custom_id="tos_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        e = discord.Embed(
            title="Commitment Acknowledgment",
            description=(
                "Before continuing, confirm that you understand this testing program is casual "
                "and payouts are intentionally small."
            ),
            color=embeds.EMBED_COLOR,
        )
        await interaction.response.edit_message(embed=e, view=CommitmentView(self.cog, self.invite_code))

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

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ) -> None:
        await log_event(
            self.cog.bot,
            "REGISTRATION_TOS_VIEW_ERROR",
            {
                "user_id": str(getattr(interaction.user, "id", "unknown")),
                "item": str(getattr(item, "custom_id", getattr(item, "label", "unknown"))),
                "error": repr(error),
            },
            level="ERROR",
        )
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    embed=embeds.warning_embed(
                        "That interaction failed.",
                        "Please run /register again.",
                    ),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    embed=embeds.warning_embed(
                        "That interaction failed.",
                        "Please run /register again.",
                    ),
                    ephemeral=True,
                )
        except discord.HTTPException:
            pass


class Registration(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._identity_cache: dict[str, dict] = {}
        self._invite_code_cache: dict[str, str] = {}

    @app_commands.command(name="register", description="Register as a UAT tester")
    @app_commands.describe(invite_code="Optional invite code (required only if owner enables it)")
    async def register(self, interaction: discord.Interaction, invite_code: str | None = None) -> None:
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
        existing = await db.get_tester(uid)
        if existing and int(existing.get("is_active", 0)):
            await interaction.response.send_message(
                embed=embeds.error_embed(
                    "You're already registered. Use /update-gcash to change your GCash number."
                ),
                ephemeral=True,
            )
            return
        if existing and not int(existing.get("is_active", 0)):
            await interaction.response.send_message(
                embed=embeds.warning_embed(
                    "Your tester account is currently deactivated.",
                    "Ask the owner to run /tester unregister if you should re-register from scratch, or /tester reactivate if you should continue your previous account.",
                ),
                ephemeral=True,
            )
            return
        latest = await db.get_latest_application(uid)
        if latest and latest.get("status") == "pending":
            await interaction.response.send_message(
                embed=embeds.error_embed("You already have a pending application. Please wait for owner review."),
                ephemeral=True,
            )
            return
        if latest and latest.get("status") == "rejected":
            reviewed_at = str(latest.get("reviewed_at") or latest.get("created_at") or "")
            if reviewed_at:
                reapply_at = datetime.fromisoformat(reviewed_at) + timedelta(days=7)
                if now_pht() < reapply_at:
                    await interaction.response.send_message(
                        embed=embeds.warning_embed(
                            "Your application was not approved.",
                            f"You may reapply after {reapply_at.strftime('%d %b %Y, %I:%M %p PHT')}.",
                        ),
                        ephemeral=True,
                    )
                    return
        invite_required = (await db.get_config("invite_code_required")).lower() == "true"
        invite_value = (await db.get_config("invite_code_value")).strip()
        if invite_required and invite_value:
            if not invite_code or invite_code.strip() != invite_value:
                await interaction.response.send_message(
                    embed=embeds.error_embed("Invalid or missing invite code."),
                    ephemeral=True,
                )
                return
        view = TOSView(self, invite_code.strip() if invite_code else None)
        await interaction.response.send_message(embed=embeds.tos_embed(), view=view, ephemeral=True)

    async def start_context_modal(self, interaction: discord.Interaction, identity_payload: dict) -> None:
        if not GCASH_RE.match(identity_payload["gcash_number"]):
            await interaction.response.send_message(
                embed=embeds.error_embed(
                    "Invalid GCash number. Use format 09XXXXXXXXX. Run /register again."
                ),
                ephemeral=True,
            )
            return
        if not identity_payload["full_name"]:
            await interaction.response.send_message(
                embed=embeds.error_embed("Full name is required."),
                ephemeral=True,
            )
            return
        uid = str(interaction.user.id)
        self._identity_cache[uid] = identity_payload
        invite_code = self._invite_code_cache.get(uid, "")
        e = embeds.confirmation_embed(
            "Step 1 complete",
            "Click **Continue to Step 2** to complete your application.",
        )
        await interaction.response.send_message(
            embed=e,
            view=ContextLaunchView(self, interaction.user.id, invite_code),
            ephemeral=True,
        )

    async def submit_application(self, interaction: discord.Interaction, context_payload: dict) -> None:
        uid = str(interaction.user.id)
        identity = self._identity_cache.pop(uid, None)
        self._invite_code_cache.pop(uid, None)
        if not identity:
            await interaction.response.send_message(
                embed=embeds.error_embed("Registration session expired. Please run /register again."),
                ephemeral=True,
            )
            return
        if not context_payload["hearing_source"] or not context_payload["tos_signature"]:
            await interaction.response.send_message(
                embed=embeds.error_embed("Required fields are missing. Please try again."),
                ephemeral=True,
            )
            return
        payload = {
            "user_id": uid,
            **identity,
            **context_payload,
        }
        created = now_pht()
        application_id = await db.create_application(payload, created)
        app_channel = await config.get_channel(self.bot, "channel_applications")
        if not app_channel:
            app_channel = await config.get_channel(self.bot, "channel_bot_logs")
        if app_channel:
            e = discord.Embed(
                title=f"New Tester Application #{application_id}",
                color=embeds.EMBED_COLOR,
                description=f"Applicant: <@{uid}> (`{uid}`)",
            )
            e.add_field(name="Display Name", value=payload["display_name"], inline=True)
            e.add_field(name="Full Name", value=payload["full_name"], inline=True)
            e.add_field(name="GCash", value=mask_gcash(payload["gcash_number"]), inline=True)
            e.add_field(name="Section/Relationship", value=payload["section_relationship"], inline=False)
            e.add_field(name="How heard", value=payload["hearing_source"], inline=False)
            e.add_field(name="Availability", value=payload.get("availability") or "—", inline=False)
            e.add_field(name="Device/Platform", value=payload.get("device_platform") or "—", inline=False)
            e.add_field(name="Prior experience", value=payload.get("prior_experience") or "—", inline=False)
            e.add_field(name="Signature", value=payload["tos_signature"], inline=False)
            e.add_field(name="Invite code", value=payload.get("invite_code") or "—", inline=False)
            e.set_footer(text="Status: pending")
            await app_channel.send(embed=e, view=ApplicationReviewView(self, application_id))
        await interaction.response.send_message(
            embed=embeds.success_embed(
                "Application submitted. You will be notified once the owner reviews it."
            ),
            ephemeral=True,
        )
        await log_event(
            self.bot,
            "APPLICATION_SUBMIT",
            {"application_id": application_id, "user_id": uid, "timestamp": created.isoformat()},
        )

    async def approve_application(self, interaction: discord.Interaction, application_id: int) -> None:
        application = await db.get_application(application_id)
        if not application or application.get("status") != "pending":
            await interaction.response.send_message("Application no longer pending.", ephemeral=True)
            return
        uid = str(application["user_id"])
        if await db.get_tester(uid):
            await db.set_application_status(application_id, "rejected", now_pht(), "Already registered.")
            await interaction.response.send_message("User is already a tester.", ephemeral=True)
            return
        try:
            enc = encrypt_gcash(str(application["gcash_number"]).strip())
        except RuntimeError:
            await interaction.response.send_message("FERNET_KEY missing. Cannot approve application.", ephemeral=True)
            return
        await db.create_tester(
            uid,
            str(application["display_name"]),
            enc,
            now_pht(),
            full_name=str(application.get("full_name") or ""),
            section_relationship=str(application.get("section_relationship") or ""),
            availability=str(application.get("availability") or ""),
            device_platform=str(application.get("device_platform") or ""),
            prior_experience=str(application.get("prior_experience") or ""),
            hearing_source=str(application.get("hearing_source") or ""),
            tos_signature=str(application.get("tos_signature") or ""),
        )
        await db.set_application_status(application_id, "approved", now_pht())
        if interaction.guild:
            role = await config.get_role(interaction.guild, "role_tester")
            member = interaction.guild.get_member(int(uid))
            if role and member:
                await member.add_roles(role, reason="Application approved")
        ws = get_week_start(today_pht())
        await db.get_or_create_earnings(uid, ws)
        user = await self.bot.fetch_user(int(uid))
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
            await user.send(
                embed=embeds.registration_success_embed(
                    str(application["display_name"]),
                    mask_gcash(str(application["gcash_number"])),
                    rates,
                    channels,
                )
            )
        except discord.HTTPException:
            pass
        if interaction.message and interaction.message.embeds:
            embed = interaction.message.embeds[0]
            embed.set_footer(text="Status: approved")
            await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message(f"Application #{application_id} approved.", ephemeral=True)
        await log_event(self.bot, "APPLICATION_APPROVE", {"application_id": application_id, "by": str(interaction.user.id)})

    async def reject_application(
        self, interaction: discord.Interaction, application_id: int, reason: str
    ) -> None:
        application = await db.get_application(application_id)
        if not application or application.get("status") != "pending":
            await interaction.response.send_message("Application no longer pending.", ephemeral=True)
            return
        await db.set_application_status(application_id, "rejected", now_pht(), reason or None)
        uid = int(application["user_id"])
        await interaction.response.send_message(
            embed=embeds.success_embed(f"Application #{application_id} rejected."),
            ephemeral=True,
        )
        try:
            user = await self.bot.fetch_user(uid)
            msg = "Your tester application was not approved."
            if reason:
                msg += f" Reason: {reason}"
            msg += " You may reapply after 7 days."
            await user.send(msg)
        except discord.HTTPException:
            pass
        await log_event(
            self.bot,
            "APPLICATION_REJECT",
            {"application_id": application_id, "by": str(interaction.user.id), "reason": reason or "none"},
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
        try:
            enc = encrypt_gcash(gcash_raw.strip())
        except RuntimeError:
            await interaction.followup.send(
                embed=embeds.warning_embed(
                    "GCash update is temporarily unavailable because bot encryption is not configured.",
                    "Please ask the owner to set FERNET_KEY in uat-bot/.env and restart the bot.",
                ),
                ephemeral=True,
            )
            await log_event(
                self.bot,
                "GCASH_UPDATE_BLOCKED",
                {"user_id": uid, "reason": "missing_fernet_key"},
                level="WARNING",
            )
            return
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

    config_group = app_commands.Group(name="config", description="Owner configuration")

    @config_group.command(name="invite-code", description="Configure invite code gate for /register")
    @app_commands.describe(required="Require invite code before registration", code="Invite code value")
    async def config_invite_code(
        self, interaction: discord.Interaction, required: bool, code: str | None = None
    ) -> None:
        if not await is_owner(interaction):
            await interaction.response.send_message(embed=embeds.error_embed("Only the bot owner can use this."), ephemeral=True)
            return
        await db.set_config("invite_code_required", "true" if required else "false")
        await db.set_config("invite_code_value", (code or "").strip())
        await interaction.response.send_message(
            embed=embeds.success_embed(
                f"Invite code gate updated. Required: {'yes' if required else 'no'}."
            ),
            ephemeral=True,
        )

    @config_group.command(name="applications-channel", description="Set private application review channel")
    async def config_applications_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        if not await is_owner(interaction):
            await interaction.response.send_message(embed=embeds.error_embed("Only the bot owner can use this."), ephemeral=True)
            return
        await db.set_config("channel_applications", str(channel.id))
        await interaction.response.send_message(
            embed=embeds.success_embed(f"Applications channel set to {channel.mention}."),
            ephemeral=True,
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
    async def tester_deactivate(self, interaction: discord.Interaction, user: discord.User) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await is_owner(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Only the bot owner can use this."),
                ephemeral=True,
            )
            return
        uid = str(user.id)
        t = await db.get_tester(uid)
        if not t or not int(t.get("is_active", 0)):
            await interaction.followup.send(
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
                member = interaction.guild.get_member(user.id)
                if role and member:
                    await member.remove_roles(role, reason="Tester deactivated")
            try:
                await user.send(
                    embed=embeds.warning_embed(
                        "Your tester account has been deactivated.",
                        "Contact the owner if you think this is a mistake.",
                    )
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
        await interaction.followup.send(
            embed=embeds.confirmation_embed(
                "Deactivate tester",
                f"Deactivate **{t.get('display_name', user.display_name)}**?",
            ),
            view=view,
            ephemeral=True,
        )

    @tester.command(name="reactivate", description="Reactivate a tester")
    @app_commands.describe(user="Tester to reactivate")
    async def tester_reactivate(self, interaction: discord.Interaction, user: discord.User) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await is_owner(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Only the bot owner can use this."),
                ephemeral=True,
            )
            return
        uid = str(user.id)
        t = await db.get_tester(uid)
        if not t or int(t.get("is_active", 0)):
            await interaction.followup.send(
                embed=embeds.error_embed("Tester not found or already active."),
                ephemeral=True,
            )
            return
        await db.reactivate_tester(uid)
        if interaction.guild:
            role = await config.get_role(interaction.guild, "role_tester")
            member = interaction.guild.get_member(user.id)
            if role and member:
                await member.add_roles(role, reason="Tester reactivated")
        try:
            await user.send(
                embed=embeds.success_embed("Your tester account has been reactivated! Welcome back.")
            )
        except discord.HTTPException:
            pass
        await log_event(
            self.bot,
            "TESTER_REACTIVATE",
            {"user_id": uid, "by": str(interaction.user.id)},
        )
        await interaction.followup.send(
            embed=embeds.success_embed("Tester reactivated."),
            ephemeral=True,
        )

    @tester.command(name="unregister", description="Fully unregister a tester from the program")
    @app_commands.describe(user="Tester to fully unregister")
    async def tester_unregister(self, interaction: discord.Interaction, user: discord.User) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await is_owner(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Only the bot owner can use this."),
                ephemeral=True,
            )
            return
        uid = str(user.id)
        tester = await db.get_tester(uid)
        if not tester:
            await interaction.followup.send(
                embed=embeds.error_embed("That user is not registered."),
                ephemeral=True,
            )
            return
        if interaction.guild:
            role = await config.get_role(interaction.guild, "role_tester")
            member = interaction.guild.get_member(user.id)
            if role and member:
                try:
                    await member.remove_roles(role, reason="Tester unregistered")
                except discord.HTTPException:
                    pass
        await db.unregister_tester(uid)
        try:
            await user.send(
                embed=embeds.confirmation_embed(
                    "UAT Unregistration Notice",
                    "Your tester account has been unregistered from the UAT program. You may apply again through /register if invited.",
                )
            )
        except discord.HTTPException:
            pass
        await log_event(
            self.bot,
            "TESTER_UNREGISTER",
            {"user_id": uid, "by": str(interaction.user.id)},
        )
        await interaction.followup.send(
            embed=embeds.success_embed(f"Unregistered {tester.get('display_name', user.display_name)}."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Registration(bot))


class ApplicationReviewView(discord.ui.View):
    def __init__(self, cog: Registration, application_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.application_id = application_id

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await is_owner(interaction):
            await interaction.response.send_message("Only owner can review applications.", ephemeral=True)
            return
        await self.cog.approve_application(interaction, self.application_id)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await is_owner(interaction):
            await interaction.response.send_message("Only owner can review applications.", ephemeral=True)
            return
        await interaction.response.send_modal(ApplicationRejectModalImpl(self.cog, self.application_id))

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ) -> None:
        await log_event(
            self.cog.bot,
            "APPLICATION_REVIEW_VIEW_ERROR",
            {
                "application_id": self.application_id,
                "user_id": str(getattr(interaction.user, "id", "unknown")),
                "item": str(getattr(item, "custom_id", getattr(item, "label", "unknown"))),
                "error": repr(error),
            },
            level="ERROR",
        )
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    embed=embeds.warning_embed(
                        "Action failed while reviewing application.",
                        "Please try again.",
                    ),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    embed=embeds.warning_embed(
                        "Action failed while reviewing application.",
                        "Please try again.",
                    ),
                    ephemeral=True,
                )
        except discord.HTTPException:
            pass







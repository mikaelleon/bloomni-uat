from __future__ import annotations

import discord

# All bot embeds use this brand color
EMBED_COLOR = 0x242429


def _embed(**kwargs) -> discord.Embed:
    return discord.Embed(color=EMBED_COLOR, **kwargs)


def tos_embed(tos_text: str | None = None) -> discord.Embed:
    body = (
        tos_text.strip()
        if tos_text and tos_text.strip()
        else (
            "By registering as a UAT tester, you agree that:\n"
            "• You will submit honest bug reports and suggestions.\n"
            "• You understand payouts are subject to owner approval and weekly caps.\n"
            "• Your GCash number is stored encrypted and only used for payouts.\n"
            "• The owner may deactivate your access at any time for rule violations."
        )
    )
    return _embed(
        title="Tester Registration — Terms of Service",
        description=f"{body}\n\nClick **I Accept** to continue or **I Decline** to cancel.",
    )


def registration_success_embed(
    display_name: str,
    masked_gcash: str,
    rates: dict,
    channels: dict,
) -> discord.Embed:
    bug_ch = channels.get("bug_reports", "#bug-reports")
    sug_ch = channels.get("suggestions", "#suggestions")
    guide_ch = channels.get("guidelines", "#tester-guidelines")
    e = _embed(
        title="Welcome to UAT Testing!",
        description=f"**Display name:** {display_name}\n**GCash (masked):** {masked_gcash}",
    )
    e.add_field(
        name="Current rates",
        value=(
            f"Bug report: ₱{rates.get('bug_report_rate', 0)}\n"
            f"Bug resolve bonus: ₱{rates.get('bug_resolve_bonus', 0)}\n"
            f"Suggestion submit: ₱{rates.get('suggestion_submit_rate', 0)}\n"
            f"Suggestion implement bonus: ₱{rates.get('suggestion_implement_bonus', 0)}"
        ),
        inline=False,
    )
    e.add_field(
        name="Where to go next",
        value=(
            f"Post bugs in {bug_ch}\n"
            f"Post suggestions via `/suggest` (posted to {sug_ch})\n"
            f"Read {guide_ch} for rules and tips."
        ),
        inline=False,
    )
    return e


def tester_profile_embed(tester: dict, all_time_stats: dict) -> discord.Embed:
    senior = "Yes" if int(tester.get("weeks_active") or 0) >= 4 else "No"
    e = _embed(
        title=f"Tester profile — {tester.get('display_name', 'Unknown')}",
        description=(
            f"**Discord user:** <@{tester['user_id']}>\n"
            f"**Registered:** {tester.get('registered_at', '—')}\n"
            f"**Active:** {'Yes' if int(tester.get('is_active', 0)) else 'No'}\n"
            f"**Weeks active:** {tester.get('weeks_active', 0)}\n"
            f"**Senior tester (4+ weeks):** {senior}"
        ),
    )
    e.add_field(
        name="All-time stats",
        value=(
            f"Bugs submitted: {all_time_stats.get('bugs_submitted', 0)}\n"
            f"Bugs resolved: {all_time_stats.get('bugs_resolved', 0)}\n"
            f"Suggestions submitted: {all_time_stats.get('suggestions_submitted', 0)}\n"
            f"Suggestions implemented: {all_time_stats.get('suggestions_implemented', 0)}\n"
            f"Total earned (all time): ₱{all_time_stats.get('total_earned_all_time', 0)}"
        ),
        inline=False,
    )
    return e


def _severity_label(sev: str) -> str:
    return {"high": "🔴 High", "medium": "🟡 Medium", "low": "🟢 Low"}.get(
        sev.lower(), sev
    )


def bug_report_embed(bug: dict, reporter: discord.User) -> discord.Embed:
    status = bug.get("status", "submitted")
    st_label = {
        "submitted": "🟡 Submitted",
        "validated": "🔵 Validated",
        "rejected": "❌ Rejected",
        "resolved": "✅ Resolved",
        "duplicate": "🔁 Duplicate",
    }.get(status, status)
    title = f"🐛 {bug['bug_id']} — {bug['title']}"
    e = _embed(title=title[:256], description=f"**Reported by:** {reporter.mention}")
    e.add_field(name="Severity", value=_severity_label(bug.get("severity", "")), inline=True)
    e.add_field(name="Status", value=st_label, inline=True)
    e.add_field(
        name="Date",
        value=str(bug.get("submitted_at", "—"))[:32],
        inline=True,
    )
    e.add_field(name="Steps to Reproduce", value=bug.get("steps", "")[:1024] or "—", inline=False)
    e.add_field(name="What Happened", value=bug.get("actual", "")[:1024] or "—", inline=False)
    e.add_field(name="What Was Expected", value=bug.get("expected", "")[:1024] or "—", inline=False)
    if bug.get("resolved_at"):
        e.add_field(name="Resolved At", value=str(bug["resolved_at"])[:64], inline=False)
    return e


def suggestion_embed(suggestion: dict, submitter: discord.User) -> discord.Embed:
    status = suggestion.get("status", "submitted")
    st_label = {
        "submitted": "🟡 Submitted",
        "acknowledged": "🔵 Acknowledged",
        "implemented": "✅ Implemented",
        "dismissed": "❌ Dismissed",
    }.get(status, status)
    title = f"💡 {suggestion['suggestion_id']} — {suggestion['title']}"
    e = _embed(title=title[:256], description=f"**Submitted by:** {submitter.mention}")
    e.add_field(name="Feature", value=suggestion.get("feature_tag", "—"), inline=True)
    e.add_field(name="Status", value=st_label, inline=True)
    e.add_field(
        name="Date",
        value=str(suggestion.get("submitted_at", "—"))[:32],
        inline=True,
    )
    e.add_field(name="Description", value=suggestion.get("description", "")[:4000] or "—", inline=False)
    if suggestion.get("dismiss_reason"):
        e.add_field(name="Dismiss reason", value=str(suggestion["dismiss_reason"])[:1024], inline=False)
    if suggestion.get("actioned_at"):
        e.add_field(name="Actioned At", value=str(suggestion["actioned_at"])[:64], inline=False)
    return e


def earnings_embed_detailed(
    display_name: str,
    week_label: str,
    bugs_submitted: int,
    bugs_validated: int,
    bugs_resolved: int,
    suggestions_submitted: int,
    suggestions_acknowledged: int,
    suggestions_implemented: int,
    earn_bug_val: int,
    earn_bug_res: int,
    earn_sug_ack: int,
    earn_sug_imp: int,
    total: int,
    cap: int,
    is_paid: bool,
) -> discord.Embed:
    e = _embed(
        title=f"📊 Weekly earnings — {display_name}",
        description=f"**Week:** {week_label}",
    )
    e.add_field(name="Bugs submitted (pending)", value=f"{bugs_submitted}", inline=False)
    e.add_field(name="Bugs validated", value=f"{bugs_validated} → +₱{earn_bug_val}", inline=False)
    e.add_field(name="Bugs resolved (bonus)", value=f"{bugs_resolved} → +₱{earn_bug_res}", inline=False)
    e.add_field(name="Suggestions submitted (pending)", value=f"{max(0, suggestions_submitted - suggestions_acknowledged)}", inline=False)
    e.add_field(name="Suggestions acknowledged", value=f"{suggestions_acknowledged} → +₱{earn_sug_ack}", inline=False)
    e.add_field(name="Suggestions implemented", value=f"{suggestions_implemented} → +₱{earn_sug_imp}", inline=False)
    e.add_field(name="Total this week", value=f"₱{total}", inline=True)
    e.add_field(name="Cap remaining", value=f"₱{max(0, cap - total)} / ₱{cap}", inline=True)
    e.add_field(name="Payout status", value="✅ Paid" if is_paid else "⏳ Pending", inline=False)
    return e


def rates_embed(config: dict) -> discord.Embed:
    e = _embed(
        title="UAT rates & limits",
        description="Current configured values.",
    )
    e.add_field(
        name="Earnings",
        value=(
            f"Bug report: ₱{config.get('bug_report_rate', '—')}\n"
            f"Bug resolve bonus: ₱{config.get('bug_resolve_bonus', '—')}\n"
            f"Suggestion submit: ₱{config.get('suggestion_submit_rate', '—')}\n"
            f"Suggestion implement bonus: ₱{config.get('suggestion_implement_bonus', '—')}"
        ),
        inline=False,
    )
    e.add_field(
        name="Limits",
        value=(
            f"Daily bug limit: {config.get('daily_bug_limit', '—')}\n"
            f"Daily suggestion limit: {config.get('daily_suggestion_limit', '—')}\n"
            f"Weekly cap: ₱{config.get('weekly_cap', '—')}"
        ),
        inline=False,
    )
    e.add_field(name="Payout", value=f"Payout day: {config.get('payout_day', 'Monday')} (PH time)", inline=False)
    return e


def warning_embed(message: str, suggestion: str | None = None) -> discord.Embed:
    description = message.strip()
    if suggestion:
        description += f"\n\n**Suggestion:** {suggestion.strip()}"
    return _embed(title="Heads up", description=description)


def error_embed(message: str) -> discord.Embed:
    # Backward-compatible alias so existing command code reads as warning-style UX.
    return warning_embed(message, "Try again, or ask an admin/owner for help if this continues.")


def success_embed(message: str) -> discord.Embed:
    return _embed(title="Success", description=message)


def confirmation_embed(title: str, description: str) -> discord.Embed:
    return _embed(title=title, description=description)


def bot_log_embed(action: str, details: dict) -> discord.Embed:
    lines = "\n".join(f"**{k}:** {v}" for k, v in details.items())
    return _embed(title=f"[LOG] {action}", description=lines[:4000] or "—")


def tester_guidelines_embed(rates: dict) -> discord.Embed:
    return _embed(
        title="Tester guidelines",
        description=(
            "Welcome! Please read these guidelines before submitting bugs or suggestions.\n\n"
            "• Use `/bug` in this server; reports are posted to the bug channel with a thread for evidence.\n"
            "• Use `/suggest` and pick the feature your idea relates to.\n"
            "• Respect daily limits and the weekly earnings cap.\n"
            "• Payouts are processed on the configured payout day (PH time).\n\n"
            f"**Current rates:** Bug ₱{rates.get('bug_report_rate', '?')}, "
            f"Resolve ₱{rates.get('bug_resolve_bonus', '?')}, "
            f"Suggestion ₱{rates.get('suggestion_submit_rate', '?')}, "
            f"Implement ₱{rates.get('suggestion_implement_bonus', '?')}, "
            f"Weekly cap ₱{rates.get('weekly_cap', '?')}."
        ),
    )


def setup_summary_embed(payload: dict) -> discord.Embed:
    e = _embed(title="Setup summary", description="Review your configuration before confirming.")
    for k, v in payload.items():
        val = str(v) if not isinstance(v, list) else "\n".join(v)
        e.add_field(name=k, value=val[:1024] or "—", inline=False)
    return e


def get_welcome_pages(
    *,
    display_name: str,
    bot_name: str,
    owner_display_name: str,
    rates: dict,
    cfg: dict,
) -> list[discord.Embed]:
    bug_val = int(rates.get("bug_report_rate", 0))
    bug_res = int(rates.get("bug_resolve_bonus", 0))
    sug_ack = int(rates.get("suggestion_submit_rate", 0))
    sug_imp = int(rates.get("suggestion_implement_bonus", 0))
    bug_daily = int(cfg.get("daily_bug_limit", 2) or 2)
    sug_daily = int(cfg.get("daily_suggestion_limit", 1) or 1)
    cap = int(cfg.get("weekly_cap", 30) or 30)
    payout_day = cfg.get("payout_day", "Monday")
    bot_desc = cfg.get("bot_description", "UAT tracking bot for reports, suggestions, and payouts.")

    pages: list[discord.Embed] = []

    p1 = discord.Embed(
        color=0x5865F2,
        title="🧪 Welcome to the UAT Tester Program!",
        description=(
            f"Hey **{display_name}**! Your application has been approved — you're now an official tester for **{bot_name}**.\n\n"
            "This DM is your complete guide to the program. You can revisit this anytime.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "What is this program?\n\n"
            f"**{bot_name}** is maintained by **{owner_display_name}**. As a tester, your job is simple: use the bot, break things, and report what can be fixed or improved.\n\n"
            "This is a casual sideline — not a job. You set your own pace.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "What you'll be testing:\n\n"
            f"{bot_desc}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
    )
    p1.set_footer(text="Page 1 of 7 • Use the buttons below to navigate")
    pages.append(p1)

    p2 = discord.Embed(
        color=0x5865F2,
        title="📋 How It Works",
        description=(
            "There are two ways to earn as a tester:\n\n"
            "🐛 **Finding Bugs**\n"
            f"- Submit with `/bug`\n- Owner validates report\n- Validated = **₱{bug_val}**\n- If resolved = **+₱{bug_res} bonus**\n\n"
            "⚠️ You earn on owner validation, not on submission.\n\n"
            "💡 **Submitting Suggestions**\n"
            f"- Submit with `/suggest`\n- Owner acknowledges it\n- Acknowledged = **₱{sug_ack}**\n- If implemented = **+₱{sug_imp} bonus**\n\n"
            "⚠️ Suggestions are also paid only after owner acknowledgment."
        ),
    )
    p2.set_footer(text="Page 2 of 7")
    pages.append(p2)

    p3 = discord.Embed(
        color=0x57F287,
        title="💰 Earning Rates & Pricing Matrix",
        description=(
            "Base Rates\n"
            f"- Bug validated: **₱{bug_val}**\n"
            f"- Bug resolved bonus: **₱{bug_res}**\n"
            f"- Suggestion acknowledged: **₱{sug_ack}**\n"
            f"- Suggestion implemented bonus: **₱{sug_imp}**\n\n"
            f"Daily limits: **{bug_daily} bugs**, **{sug_daily} suggestion(s)**\n"
            f"Weekly cap: **₱{cap}**\n\n"
            f"Max per validated bug: **₱{bug_val + bug_res}**\n"
            f"Max per implemented idea: **₱{sug_ack + sug_imp}**"
        ),
    )
    p3.set_footer(text="Page 3 of 7 • Rates may increase as milestones are reached")
    pages.append(p3)

    p4 = discord.Embed(
        color=0xFEE75C,
        title="⏱️ Limits, Resets & Real Earnings Examples",
        description=(
            "Limits and resets:\n"
            f"- Bugs/day: **{bug_daily}** (resets midnight PHT)\n"
            f"- Suggestions/day: **{sug_daily}** (resets midnight PHT)\n"
            f"- Weekly cap: **₱{cap}** (resets Monday midnight PHT)\n\n"
            "Use `/myinfo` for live usage and countdown timers.\n\n"
            "Validation timing matters: earnings are credited when owner action happens, not when you submit."
        ),
    )
    p4.set_footer(text="Page 4 of 7")
    pages.append(p4)

    p5 = discord.Embed(
        color=0xEB459E,
        title="💸 How Payouts Work",
        description=(
            f"Payouts are sent every **{payout_day}** via GCash.\n\n"
            "No minimum payout. If you earned it, it gets paid.\n\n"
            "If payout seems missing:\n"
            "1) Check `/myinfo` for masked GCash\n"
            "2) Update with `/update-gcash` if needed\n"
            "3) DM the owner privately"
        ),
    )
    p5.set_footer(text="Page 5 of 7")
    pages.append(p5)

    p6 = discord.Embed(
        color=0x5865F2,
        title="🤖 Your Commands — Quick Reference",
        description=(
            "**Profile:** `/myinfo`, `/mybugs`, `/mysuggestions`, `/mypending`, `/streak`\n"
            "**Submit:** `/bug`, `/suggest`\n"
            "**Earnings:** `/earnings`, `/history`, `/rates`\n"
            "**Community:** `/leaderboard`\n"
            "**Account:** `/update-gcash`\n"
            "**Browse:** `/bugs list`, `/bugs info`, `/suggestion list`, `/suggestion info`"
        ),
    )
    p6.set_footer(text="Page 6 of 7 • All commands are slash commands")
    pages.append(p6)

    p7 = discord.Embed(
        color=0xED4245,
        title="📜 Rules & Reminders",
        description=(
            "1) Quality over quantity.\n"
            "2) One submission per issue.\n"
            "3) Include clear steps and evidence.\n"
            "4) Use bug threads for screenshots/recordings.\n"
            "5) Keep feedback civil and constructive.\n"
            "6) Keep your GCash details updated.\n\n"
            "Need help? DM the owner for payout/account concerns.\n\n"
            "You're all set. Happy testing! 🧪"
        ),
    )
    p7.set_footer(text="Page 7 of 7 • You can revisit this guide anytime in this DM")
    pages.append(p7)
    return pages

from __future__ import annotations

import discord

# All bot embeds use this brand color
EMBED_COLOR = 0x242429


def _embed(**kwargs) -> discord.Embed:
    return discord.Embed(color=EMBED_COLOR, **kwargs)


def tos_embed() -> discord.Embed:
    return _embed(
        title="Tester Registration — Terms of Service",
        description=(
            "By registering as a UAT tester, you agree that:\n"
            "• You will submit honest bug reports and suggestions.\n"
            "• You understand payouts are subject to owner approval and weekly caps.\n"
            "• Your GCash number is stored encrypted and only used for payouts.\n"
            "• The owner may deactivate your access at any time for rule violations.\n\n"
            "Click **I Accept** to continue or **I Decline** to cancel."
        ),
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

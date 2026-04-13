import discord


class RegistrationModal(discord.ui.Modal, title="Tester Registration"):
    display_name = discord.ui.TextInput(
        label="Display Name",
        placeholder="What should we call you?",
        max_length=50,
        required=True,
    )
    gcash_number = discord.ui.TextInput(
        label="GCash Mobile Number",
        placeholder="09XXXXXXXXX",
        max_length=11,
        min_length=11,
        required=True,
    )


class UpdateGCashModal(discord.ui.Modal, title="Update GCash"):
    gcash_number = discord.ui.TextInput(
        label="New GCash Number",
        placeholder="09XXXXXXXXX",
        max_length=11,
        min_length=11,
        required=True,
    )


class BugReportModal(discord.ui.Modal, title="Bug Report"):
    bug_title = discord.ui.TextInput(
        label="Bug Title",
        placeholder="Short, clear title",
        max_length=100,
        required=True,
    )
    steps = discord.ui.TextInput(
        label="Steps to Reproduce",
        style=discord.TextStyle.paragraph,
        placeholder="1. Do this\n2. Then this\n3. Then this",
        required=True,
    )
    actual = discord.ui.TextInput(
        label="What Happened",
        style=discord.TextStyle.paragraph,
        placeholder="Describe what actually happened",
        required=True,
    )
    expected = discord.ui.TextInput(
        label="What Was Expected",
        style=discord.TextStyle.paragraph,
        placeholder="Describe what should have happened",
        required=True,
    )


class SuggestionModal(discord.ui.Modal, title="Suggestion"):
    title_field = discord.ui.TextInput(
        label="Suggestion Title",
        placeholder="Short, clear title",
        max_length=100,
        required=True,
    )
    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        placeholder="Describe your suggestion in detail",
        required=True,
    )


class RatesSetupModal(discord.ui.Modal, title="Edit Rates"):
    """Discord allows max 5 text inputs; use one block matching DEFAULT_CONFIG keys."""

    rates_text = discord.ui.TextInput(
        label="Rates (one per line: key: value)",
        style=discord.TextStyle.paragraph,
        placeholder=(
            "bug_report_rate: 15\n"
            "bug_resolve_bonus: 10\n"
            "suggestion_submit_rate: 10\n"
            "suggestion_implement_bonus: 15\n"
            "weekly_cap: 250\n"
            "daily_bug_limit: 3\n"
            "daily_suggestion_limit: 2"
        ),
        required=True,
        max_length=1000,
    )


class FeaturesEditModal(discord.ui.Modal, title="Edit Features"):
    features = discord.ui.TextInput(
        label="Features (one per line)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000,
    )


class MilestoneModal(discord.ui.Modal, title="Add Milestone"):
    name = discord.ui.TextInput(label="Milestone name", required=True, max_length=200)
    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000,
    )
    rate_changes = discord.ui.TextInput(
        label="Rate changes",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000,
    )


class ExistingRolesModal(discord.ui.Modal, title="Map existing roles"):
    admin_role = discord.ui.TextInput(
        label="UAT Admin role ID or mention",
        required=True,
        max_length=30,
    )
    tester_role = discord.ui.TextInput(
        label="Tester role ID or mention",
        required=True,
        max_length=30,
    )
    senior_role = discord.ui.TextInput(
        label="Senior Tester role ID or mention",
        required=True,
        max_length=30,
    )


class ExistingChannelsModal(discord.ui.Modal, title="Map existing channels"):
    """Max 5 modal fields in Discord; use ordered list of channel IDs (one per line)."""

    mapping = discord.ui.TextInput(
        label="Channel IDs (7 lines: order in description)",
        style=discord.TextStyle.paragraph,
        placeholder="7 lines: announcements, register, bugs, suggestions, payout, logs, guidelines",
        required=True,
        max_length=1000,
    )


class BugReopenModal(discord.ui.Modal, title="Reopen bug"):
    reason = discord.ui.TextInput(
        label="Reason for reopening (optional)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=2000,
    )


class SuggestionDismissModal(discord.ui.Modal, title="Dismiss suggestion"):
    reason = discord.ui.TextInput(
        label="Reason for dismissal (optional)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=2000,
    )

# Setup and Configuration

## Commands

| Command | Who | Purpose |
|---------|-----|---------|
| `/setup` | Bot owner | Interactive wizard: roles, channels, rates, features, milestones, summary, confirm. |
| `/setup_reset` | Bot owner | Destroys data / resets DB; confirmation required. On Windows, if the SQLite file is locked, the bot may reset in place instead of deleting the file. |

## What `/setup` configures

- **Roles:** UAT Admin, Tester, Senior Tester (create new or map existing with click-to-select flows).
- **Channels:** category + text channels (or map existing), including:
  - announcements, register-here, bug-reports, suggestions, payout-log, bot-logs, tester-guidelines  
  - **Applications** channel: set later with **`/config applications-channel`** if you want a private review room (otherwise applications may fall back to bot logs).
- **Rates and limits** (seven values): bug report rate, bug resolve bonus, suggestion submit rate, suggestion implement bonus, weekly cap, daily bug limit, daily suggestion limit.
- **Feature list** for `/suggest` (Step 4 modal; `Other` preserved).
- **Optional milestones** (stored for future use; full milestone command suite may be incomplete).

## Navigation

- Steps use views with **Next**, **Back**, **Skip**, **Cancel** where applicable.
- Role/channel mapping can auto-advance on selection; final **review** section supports **Back/Next** between summary sections before **Confirm**.

## After setup

- `setup_complete` is set; guidelines embed can be posted/pinned in guidelines channel.
- Owners should set **`/config applications-channel`** to a private staff-only channel for tester applications if not created during an older setup flow.

## Ongoing owner configuration (outside the wizard)

These live under the **`/config`** group in the Registration cog:

| Subcommand | Purpose |
|------------|---------|
| `invite-code` | `required` + optional `code` string. |
| `applications-channel` | Where application embeds with Approve/Reject are posted. |
| `set` | Choices: `bot_description`, `tos_text`, and all seven numeric keys. Text keys accept any string; numeric keys must be integers. Blocked for numeric keys when `economy_mode` is `auto`. |
| `economy-mode` | `manual` or `auto`. |
| `economy-auto` | Parameters: `weekly_cap`, `daily_bug_limit`, `daily_suggestion_limit`, plus optional weight/bonus percentages; computes all four rates and saves limits/cap. |
| `rates` | Opens a **modal** to edit all seven numbers at once (then follows same broadcast behavior as manual rate updates when applicable). |
| `changes` | Subcommands: `channel`, `enabled`, `status`, `test` — GitHub push announcements (see [FEATURE_Change_Announcements.md](./FEATURE_Change_Announcements.md)). |

## Logging

- Setup completion and errors are logged when `channel_bot_logs` is configured; destructive reset failures are surfaced to the user and logged.

## Output examples

- Success: “Setup complete! Guidelines posted and pinned.”
- Guard: “Only the bot owner can run setup.”

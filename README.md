# Bloomni UAT Tracker Bot

A Discord bot for small private teams running User Acceptance Testing (UAT): **screen registrations**, **track bugs and suggestions**, and **calculate weekly earnings** with clear owner validation steps.

This README is written so non-technical readers can understand what the bot does and how to run it.

## Table of Contents

- [What This Bot Does](#what-this-bot-does)
- [What This Bot Does Not Do Yet](#what-this-bot-does-not-do-yet)
- [How It Works in Plain English](#how-it-works-in-plain-english)
- [Permissions and Roles](#permissions-and-roles)
- [Setup Guide (Step-by-Step)](#setup-guide-step-by-step)
- [Command Reference by Permission](#command-reference-by-permission)
- [Feature Overview](#feature-overview)
- [Documentation Files](#documentation-files)
- [Logging and Safety](#logging-and-safety)
- [Local Development](#local-development)
- [Troubleshooting](#troubleshooting)

## What This Bot Does

- Runs a guided **first-time setup** for roles, channels, rates, suggestion feature tags, and optional milestones.
- **Application-based registration:** applicants complete two modals; the owner **approves or rejects** in a private applications channel; optional **invite code** gate.
- Encrypts **GCash** numbers at rest (Fernet).
- Accepts **bug** submissions (severity + modal); **owner validates** before report pay; **owner resolves** for resolve bonus (bug must be validated first).
- Accepts **suggestions** (feature tag + modal); **owner acknowledges** before submit pay; **owner implements** for implement bonus.
- Tracks **weekly earnings**, **daily limits**, and **weekly cap**; supports **manual** rates or **auto-calculated** economy from cap + daily limits.
- **Broadcasts** rate changes to announcements and can **resend** the 7-page DM guide to all active testers when rates change (manual path / economy-auto / rates modal).
- **Tester commands:** `/myinfo` (live reset countdowns), `/mybugs`, `/mysuggestions`, `/mypending`, `/streak`, `/history`, `/leaderboard`, plus `/earnings` and `/rates`.
- **Tester removal:** deactivate or unregister can **remove** that tester’s bugs from the database, **close** threads, and **renumber** remaining bug IDs (`BUG-001`, `BUG-002`, …).
- Optional **GitHub push announcements:** when `CHANGELOG_HTTP_ENABLED` is set and a GitHub webhook hits `/webhooks/github`, the bot can post an embed (commit subject lines + compare link) to a channel you set with **`/config changes`**.
- Logs major actions to a private **bot log** channel when configured.
- Uses a consistent embed color: **`#242429`**.

## What This Bot Does Not Do Yet

These are **not** fully implemented as described in older design drafts:

- Full **payout** suite (`/payout generate`, `/payout confirm`, `/payout gcash`, `/payout history`) — earnings and “paid” flags exist, but not a complete payout workflow.
- **Automated** weekly reminders, scheduled weekly resets, and **patch** announcement commands.
- Complete **milestone** command suite (milestone data may exist from setup; reaching milestones via commands may be incomplete).

**Implemented note:** `/leaderboard` **is** available (ranks testers by **total weekly earnings** for the current week).

## How It Works in Plain English

1. Owner runs **`/setup`** once.
2. Owner sets **`/config applications-channel`** to a private channel (recommended) and optionally **`/config invite-code`**.
3. Members run **`/register`** in the register channel; after approval they get the **Tester** role and a **paginated DM guide**.
4. Testers file **bugs** and **suggestions**; **no** report/submit pay until the **owner validates / acknowledges**.
5. Owner **resolves** bugs and **implements** suggestions for bonuses; earnings stay under the **weekly cap**.
6. Testers use **`/myinfo`**, **`/earnings`**, and related commands to track progress.

## Permissions and Roles

- **`UAT Admin`:** extra visibility (e.g. `/tester list`, viewing others’ earnings).
- **`Tester`:** required for normal tester commands after approval.
- **`Senior Tester`:** tracked toward **4+ active weeks** (loyalty / display); automatic loyalty payouts may depend on future scheduling features.

**Permission levels in slash commands:**

- **Bot owner** (env `OWNER_ID`) — setup, config, bug/suggestion moderation, tester deactivate/unregister.
- **Admin** — `/tester info @user`, `/tester list`, `/earnings @user` (as implemented in `utils/checks`).
- **Active tester** — submission and personal stats commands.

## Setup Guide (Step-by-Step)

### 1) Create `.env` in `uat-bot/`

```env
BOT_TOKEN=your_discord_bot_token
OWNER_ID=your_discord_user_id
FERNET_KEY=your_generated_fernet_key
```

Optional (guild sync for faster command updates while developing):

```env
SYNC_GUILD_ID=your_guild_id
```

Optional (repository push → Discord; see `docs/FEATURE_Change_Announcements.md`):

```env
CHANGELOG_HTTP_ENABLED=false
CHANGELOG_HTTP_PORT=8765
GITHUB_WEBHOOK_SECRET=your_github_webhook_secret
```

Generate `FERNET_KEY` with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2) Install dependencies

```bash
cd uat-bot
pip install -r requirements.txt
```

### 3) Run the bot

```bash
python bot.py
```

### 4) In Discord, run `/setup`

Complete the wizard, then configure:

- `/config applications-channel` → private **#applications** (or similar)
- `/config invite-code` if you want a referral/invite gate

## Command Reference by Permission

Detailed tables: **[docs/COMMANDS_By_Permission.md](docs/COMMANDS_By_Permission.md)**.

**Owner (summary):** `/setup`, `/setup_reset`, `/config …` (including **`/config changes`** for Git push announcements), `/bugs validate`, `/bugs reject`, `/bugs resolve`, `/bugs reopen`, `/suggestion acknowledge`, `/suggestion implement`, `/suggestion dismiss`, `/tester deactivate`, `/tester reactivate`, `/tester unregister`.

**Admin:** `/tester info @user`, `/tester list`, `/earnings @user`.

**Active tester:** `/update-gcash`, `/tester info`, `/bug`, `/bugs submit`, `/bugs list`, `/bugs info`, `/suggest`, `/suggestion list`, `/suggestion info`, `/earnings`, `/rates`, `/myinfo`, `/mybugs`, `/mysuggestions`, `/mypending`, `/streak`, `/history`, `/leaderboard`.

**Register channel:** `/register [invite_code]`.

## Feature Overview

| Topic | Doc |
|--------|-----|
| Setup wizard & `/config` | [docs/FEATURE_Setup_and_Configuration.md](docs/FEATURE_Setup_and_Configuration.md) |
| Registration, applications, testers | [docs/FEATURE_Registration_and_Testers.md](docs/FEATURE_Registration_and_Testers.md) |
| Bugs (validate/reject/resolve) | [docs/FEATURE_Bugs.md](docs/FEATURE_Bugs.md) |
| Suggestions (acknowledge/implement) | [docs/FEATURE_Suggestions.md](docs/FEATURE_Suggestions.md) |
| Earnings, `/myinfo`, leaderboard | [docs/FEATURE_Earnings_and_Rates.md](docs/FEATURE_Earnings_and_Rates.md) |
| Git push → Discord embeds | [docs/FEATURE_Change_Announcements.md](docs/FEATURE_Change_Announcements.md) |

## Documentation Files

- **[docs/COMMANDS_By_Permission.md](docs/COMMANDS_By_Permission.md)** — Slash commands by role.
- **[docs/FEATURE_*.md](docs/)** — One file per area (setup, registration, bugs, suggestions, earnings, change announcements).
- **[docs/UAT_Bot_Features.md](docs/UAT_Bot_Features.md)** — Original long-form design spec (partly aspirational; use README + FEATURE docs for current behavior).
- **[docs/UAT_Bot_Implementation_Prompt.md](docs/UAT_Bot_Implementation_Prompt.md)** — Implementation prompt used to build the project.

## Logging and Safety

- Important actions can be logged to **`channel_bot_logs`** (warnings/suggestions phrasing in code where applicable).
- **Never commit** `.env` or real tokens. If a token was committed, **rotate** it in the Discord Developer Portal.
- GCash is stored **encrypted**; profile commands do **not** show full GCash numbers.

## Local Development

- Entry: `uat-bot/bot.py`
- Database: SQLite (`uat_bot.db` by default), schema under `uat-bot/database/`
- Cogs: `uat-bot/cogs/`
- UI: `uat-bot/ui/`
- Utilities: `uat-bot/utils/`

## Troubleshooting

- **“Bot has not been set up”** — Owner runs `/setup`.
- **“Please head to #register-here”** — Use `/register` only in the configured register channel.
- **Tester commands fail** — Ensure the member has the **Tester** role and `is_active` in the database.
- **FERNET_KEY errors on approval** — Set `FERNET_KEY` in `.env` and restart; without it, approvals that need encryption will fail.
- **Commands missing in Discord** — Set `SYNC_GUILD_ID` for instant guild sync, or wait for global command propagation.
- **Interaction / “Unknown interaction” errors** — Usually fixed in current code by deferring early; update to latest `uat-bot` and restart.

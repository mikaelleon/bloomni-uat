# Bloomni UAT Tracker Bot

A Discord bot that helps small private teams run User Acceptance Testing (UAT):
register testers, collect bug reports and suggestions, and track weekly earnings.

This guide is intentionally simple and non-technical.

## Table of Contents

- [What This Bot Does](#what-this-bot-does)
- [What This Bot Does Not Do Yet](#what-this-bot-does-not-do-yet)
- [How It Works in Plain English](#how-it-works-in-plain-english)
- [Permissions and Roles](#permissions-and-roles)
- [Setup Guide (Step-by-Step)](#setup-guide-step-by-step)
- [Command Reference by Permission](#command-reference-by-permission)
- [Feature Overview](#feature-overview)
- [Logging and Safety](#logging-and-safety)
- [Local Development](#local-development)
- [Troubleshooting](#troubleshooting)

## What This Bot Does

- Runs a guided first-time setup for required roles/channels/rates.
- Registers testers securely (GCash encrypted at rest).
- Accepts bug submissions with severity and evidence thread creation.
- Accepts suggestions with feature tagging.
- Lets owner resolve/reopen bugs and implement/dismiss suggestions.
- Tracks weekly earnings and limits.
- Shows personal and admin-view earnings and tester profiles.
- Logs major actions to a private bot log channel.

## What This Bot Does Not Do Yet

These are intentionally out of scope for the current release:

- Full payout command set (`/payout generate`, `/payout confirm`, `/payout gcash`, `/payout history`)
- Leaderboard command
- Automated weekly payout/reminder tasks
- Milestone command suite (milestone data exists, but command set is not complete)

## How It Works in Plain English

1. Owner runs setup once.
2. Members register in the register channel.
3. Testers submit bugs and suggestions.
4. Owner marks outcomes (resolved/implemented/dismissed).
5. Bot updates each tester's weekly earnings and limits.
6. Everyone can see what they submitted and what they earned.

## Permissions and Roles

The bot uses three main roles:

- `UAT Admin`: can view/manage more than regular testers.
- `Tester`: required for normal tester commands.
- `Senior Tester`: reserved for future bonus logic.

Permission levels used in commands:

- Owner Only
- Admin (and owner)
- Active Tester

## Setup Guide (Step-by-Step)

### 1) Create `.env` in `uat-bot/`

Use this format:

```env
BOT_TOKEN=your_discord_bot_token
OWNER_ID=your_discord_user_id
FERNET_KEY=your_generated_fernet_key
```

Generate `FERNET_KEY` with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2) Install dependencies

```bash
cd "uat-bot"
pip install -r requirements.txt
```

### 3) Run the bot

```bash
python bot.py
```

### 4) In Discord, run `/setup`

Use the wizard to:

- create/map roles
- create/map channels
- set rates and limits
- edit feature dropdown options
- add optional milestones
- confirm setup

When done, the bot posts/pins guidelines in the guidelines channel.

## Command Reference by Permission

### Owner Only

- `/setup`
- `/setup_reset`
- `/tester deactivate`
- `/tester reactivate`
- `/bugs resolve`
- `/bugs reopen`
- `/suggestion implement`
- `/suggestion dismiss`

### Admin (Owner also allowed)

- `/tester info @user`
- `/tester list`
- `/earnings @user`

### Active Tester

- `/update-gcash`
- `/tester info`
- `/bug` (submit)
- `/bugs submit`
- `/bugs list`
- `/bugs info`
- `/suggest`
- `/suggestion list`
- `/suggestion info`
- `/earnings`
- `/rates`

### Registration / Unregistered Entry

- `/register` (must be in configured register channel)

## Feature Overview

### Setup Wizard

- Interactive role/channel/rate/feature/milestone setup
- Summary before confirmation
- Setup completion flag in DB

### Registration

- TOS acceptance/decline flow
- GCash validation (`09XXXXXXXXX`)
- encrypted GCash storage
- tester role assignment

### Bugs

- severity selector before modal
- duplicate title warning (Jaccard similarity)
- channel post + evidence thread creation
- resolve/reopen lifecycle

### Suggestions

- feature dropdown from config list
- pending/implemented/dismissed lifecycle
- owner moderation flow

### Earnings

- weekly counters and totals
- daily bug/suggestion caps
- weekly earnings cap

## Logging and Safety

- Key actions are logged to `channel_bot_logs`.
- GCash is encrypted using Fernet before saving.
- `.env` must never be committed.
- Embeds use a consistent theme color: `#242429`.

## Local Development

Project root here contains docs and `uat-bot/` source code.

- Entry: `uat-bot/bot.py`
- Database: `uat-bot/database/`
- Commands: `uat-bot/cogs/`
- UI helpers: `uat-bot/ui/`
- Utilities: `uat-bot/utils/`

## Troubleshooting

- "Bot has not been set up": run `/setup` as owner.
- "Please head to #register-here": use `/register` in configured register channel.
- Can't use tester commands: verify tester is active and has Tester role.
- Missing channel/role behavior: rerun `/setup_reset` then `/setup`.
- Push blocked by secret scanning: rotate token and ensure `.env` is ignored.

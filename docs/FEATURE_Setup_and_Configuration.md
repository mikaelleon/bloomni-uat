# Setup and Configuration Guide

This document explains everything in the `/setup` and `/setup_reset` workflow.

## Commands in This Group

- `/setup` (Owner only)
- `/setup_reset` (Owner only)

## Purpose

`/setup` prepares your server so the bot can work safely without hardcoded IDs.

## What `/setup` Configures

- Roles:
  - `UAT Admin`
  - `Tester`
  - `Senior Tester`
- Channels:
  - `#uat-announcements`
  - `#register-here`
  - `#bug-reports`
  - `#suggestions`
  - `#payout-log`
  - `#bot-logs`
  - `#tester-guidelines`
- Rates and limits:
  - bug report rate
  - bug resolve bonus
  - suggestion submit rate
  - suggestion implement bonus
  - weekly cap
  - daily bug limit
  - daily suggestion limit
- Feature dropdown list for suggestions
- Optional milestones

## Step-by-Step Logic

### Step 1: Roles

- Owner chooses `Create New` or `Use Existing`.
- Create mode creates all three roles.
- Existing mode accepts role IDs/mentions and saves mappings.

### Step 2: Channels

- Owner chooses `Create New` or `Use Existing`.
- Create mode builds category + channels with basic permissions.
- Existing mode accepts seven channel IDs in expected order.

### Step 3: Rates

- Owner can open modal and paste `key: value` lines.
- Or choose defaults from current session config.

### Step 4: Features

- Owner edits suggestion feature list.
- Bot always ensures `Other` is available.

### Step 5: Milestones

- Optional. Owner can add one or many milestone records.

### Step 6: Summary + Confirm

- Bot shows setup summary embed.
- On confirm:
  - `setup_complete=true`
  - guidelines embed posted and pinned
  - setup session cleared

## `/setup_reset` Behavior

- Shows confirmation buttons.
- On confirm, DB is rebuilt and setup can be rerun.

## Output Examples

### Success output

- "Setup complete! Guidelines posted and pinned."

### Warning output examples

- "Only the bot owner can run setup."
- "Provide exactly 7 channel IDs (one per line)."

## Logging

- Setup completion and key setup actions are logged in bot logs when configured.

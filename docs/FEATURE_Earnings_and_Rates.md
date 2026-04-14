# Earnings and Rates

Covers `/earnings`, `/rates`, `/myinfo`, `/mybugs`, `/mysuggestions`, `/mypending`, `/streak`, `/history`, `/leaderboard`, and how owner config ties in.

## `/earnings`

### Access

- No argument: active tester sees **own** weekly row.
- `@user`: **admin** (or owner) only.

### Logic

- Week boundary: Monday start in **Asia/Manila** (`get_week_start`).
- Loads/creates the `earnings` row for that week.
- **Displayed math** uses:
  - `bugs_validated` × bug report rate  
  - `bugs_resolved` × resolve bonus  
  - `suggestions_acknowledged` × suggestion submit rate  
  - `suggestions_implemented` × implement bonus  
- `bugs_submitted` / `suggestions_submitted` counters may still exist for stats but **paid amounts** follow validated/acknowledged/resolved/implemented columns.
- Shows total earned vs weekly cap and paid flag.

## `/rates`

- Ephemeral embed from full config: all four rates, daily limits, weekly cap, payout day, **economy mode** (`manual` / `auto`), etc.

## `/myinfo`

- Active tester only.
- Pulls **live** `daily_bug_limit`, `daily_suggestion_limit`, `weekly_cap` from config.
- **Daily reset** and **weekly reset** use Discord relative timestamps: `<t:UNIX:R>`.
- Shows today’s usage, week-to-date earnings, **pending** counts (bugs in `submitted`, suggestions in `submitted`) with “pending validation / acknowledgement” peso hints using current rates.
- All-time stats block from `get_tester_all_time_stats`.

## Other tester commands (same cog)

| Command | Role | Notes |
|---------|------|--------|
| `/mybugs` | Active tester | Paginated list of your bugs; optional `status` filter. |
| `/mysuggestions` | Active tester | Paginated list of your suggestions; optional `status` filter. |
| `/mypending` | Active tester | Counts of `submitted` bugs and `submitted` suggestions. |
| `/streak` | Active tester | Consecutive active weeks and senior (4+ weeks) progress. |
| `/history` | Active tester | Past weekly rows; optional `week` index. |
| `/leaderboard` | Anyone who can invoke | Top **10** users by **`total_earned`** for the **current** week (not “validated-only” ranking). |

## Owner-driven rate changes

- **`/config set`** with a numeric key: if economy mode is **manual** and a rate/limit changed, the bot can **announce** in the announcements channel and **resend** the 7-page DM guide to all active testers (`_broadcast_rate_update`).
- **`/config economy-auto`**: sets mode to **auto**, writes computed rates + limits, then broadcasts the same way.
- In **auto** mode, **`/config set`** is blocked for numeric rate keys until you switch to manual or run `economy-auto` again.

## Data sources

- `earnings` table: weekly counters and `total_earned`, `is_paid`.
- `config` table: rates, limits, `economy_mode`, `bot_description`, `tos_text`, channels, etc.

## DM quality for money events

- Bug validate, bug resolve, suggestion acknowledge, suggestion implement send **rich embeds** to the user with a **Current stats** field (weekly balance, cap remaining, daily bug/suggestion slots left).

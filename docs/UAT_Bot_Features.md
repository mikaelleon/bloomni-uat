# UAT Tracking Bot — Full Feature Specification
### Built with discord.py v2.x

> **Role Legend used in this document:**
> - 🔴 **Owner Only** — Bot owner (hardcoded Discord User ID) or a designated "Bot Owner" role
> - 🟡 **Admin** — Server admin or a designated "UAT Admin" role
> - 🟢 **Tester** — Any registered tester with the "Tester" role
> - ⚪ **Unregistered** — Any server member without the Tester role

---

---

# PART 0 — SERVER SETUP & CONFIGURATION WIZARD

> Run this once when the bot is first added to the server. It creates and configures all required channels, roles, and settings automatically.

---

## `/setup`
**🔴 Owner Only**

Starts the interactive setup wizard. The bot walks through each step one at a time using button-based navigation (Next / Skip / Cancel). No manual channel or role creation needed.

---

### Step 1 — Role Creation

Bot automatically creates the following roles if they don't already exist:

| Role Name | Color | Purpose |
|---|---|---|
| `UAT Admin` | 🟡 Yellow | Can run admin-level commands |
| `Tester` | 🟢 Green | Granted after registration; required to use bot commands |
| `Senior Tester` | 🔵 Blue | Automatically assigned after 4+ active weeks; unlocks loyalty bonus |

Bot asks: *"Should I create these roles now, or would you like to assign existing roles instead?"*
- **Create New** → Bot makes them automatically
- **Use Existing** → Bot sends a follow-up prompt asking you to mention which existing roles map to each

---

### Step 2 — Channel Creation

Bot automatically creates the following channels inside a new `📋 UAT Testing` category:

| Channel Name | Type | Purpose |
|---|---|---|
| `#uat-announcements` | Text | Patch notes, milestone announcements, weekly reminders |
| `#register-here` | Text | Where members run `/register` |
| `#bug-reports` | Text | All bug report embeds + threads are posted here |
| `#suggestions` | Text | All suggestion embeds are posted here |
| `#payout-log` | Text | Payout confirmations and earnings notifications |
| `#bot-logs` | Text (private) | All bot actions logged here; visible to Owner + Admin only |
| `#tester-guidelines` | Text (read-only) | Auto-posted guidelines and current rates |

Bot asks: *"Should I create these channels now, or would you like to point me to existing ones?"*
- **Create New** → Bot makes the category and all channels
- **Use Existing** → Bot sends follow-up prompts asking you to `#mention` each existing channel

---

### Step 3 — Rate Configuration

Bot sends an embed asking you to set the starting payout rates via a modal form:

| Setting | Default Value | Description |
|---|---|---|
| Bug report rate | ₱15 | Paid on submission of a valid bug |
| Bug resolve bonus | ₱10 | Bonus paid when owner resolves the bug |
| Suggestion submit rate | ₱10 | Paid on submission of a clear suggestion |
| Suggestion implement bonus | ₱15 | Bonus paid when owner implements it |
| Weekly payout cap | ₱250 | Max any one tester can earn per week |
| Daily bug limit | 3 | Max bugs a tester can submit per day |
| Daily suggestion limit | 2 | Max suggestions a tester can submit per day |

All values are editable after setup via `/config set`.

---

### Step 4 — Feature Dropdown Options

Bot asks you to define the list of features testers can tag when submitting suggestions. A modal opens with a text field — enter each feature name on a new line. These become the dropdown options in `/suggest`.

Example defaults provided:
```
Commission System
Bug Tracker
Payout System
Registration
Other
```

Editable after setup via `/config features`.

---

### Step 5 — Milestone Configuration

Bot asks if you want to pre-define any milestones and their rate changes now, or skip and add them later via `/milestone add`.

If you proceed, a modal opens:
- Milestone name (e.g. "v1.0 Stable Release")
- What changes when it's reached (e.g. bug rate → ₱30, weekly cap → ₱350)

---

### Step 6 — Summary & Confirmation

Bot posts a full summary embed of everything configured:
- Roles created/mapped
- Channels created/mapped
- Current rates
- Feature dropdown list
- Timezone (auto-set to **Asia/Manila, PH Time**)

Two buttons: **✅ Confirm Setup** | **🔄 Start Over**

On confirm, bot posts the tester guidelines embed in `#tester-guidelines` and pins it automatically.

---

### `/setup reset`
**🔴 Owner Only**

Wipes all bot data (database, config) and re-runs the setup wizard from Step 1. Bot asks for confirmation before proceeding — this is irreversible.

---

---

# PART 1 — REGISTRATION SYSTEM

---

## `/register`
**⚪ Unregistered Members**

The entry point for all new testers. Can only be run in `#register-here`. If run anywhere else, bot replies with an ephemeral error pointing them to the right channel.

---

### Flow

**Step 1 — TOS Display**

Bot sends an ephemeral embed in-server (only the user can see it) containing the full Terms of Service. At the bottom, two buttons appear:

- **✅ I Accept** — proceeds to Step 2
- **❌ I Decline** — bot sends ephemeral message: *"Registration cancelled. Come back when you're ready!"* and the interaction ends

---

**Step 2 — Registration Modal**

Triggered when user clicks **I Accept**. A modal form opens with the following fields:

| Field | Type | Required | Notes |
|---|---|---|---|
| Display Name | Short text | ✅ | What they want to be called in payouts/embeds |
| GCash Mobile Number | Short text | ✅ | Must be 11 digits; bot validates format |

On submit, bot validates the GCash number format (`09XXXXXXXXX`). If invalid, bot replies with an ephemeral error and lets them resubmit.

---

**Step 3 — Completion**

On successful submission:
- Bot assigns them the **Tester** role
- Bot sends an ephemeral in-server confirmation: *"You're registered! Check your DMs."*
- Bot DMs them a welcome embed containing:
  - Their Display Name and registered GCash number (masked: `09XX****XXX`)
  - Current earning rates
  - Links to `#bug-reports` and `#suggestions`
  - A reminder to check `#tester-guidelines`
- Bot logs the registration in `#bot-logs`

---

### Guard Behavior

- If an already-registered user runs `/register` again → ephemeral reply: *"You're already registered! Use `/update-gcash` if you need to change your GCash number."*
- All other bot commands (`/bug`, `/suggest`, `/earnings`, etc.) check for the Tester role before running. If not registered, they reply: *"You need to register first. Head to #register-here and run /register."*

---

## `/update-gcash`
**🟢 Tester**

Allows a tester to update their GCash number without re-registering.

Opens a small modal with one field: **New GCash Number**

On submit:
- Bot validates the format
- Updates the database
- DMs the tester a confirmation with the new masked number
- Logs the change in `#bot-logs`

---

## `/tester info [@user]`
**🟢 Tester** (own profile) | **🟡 Admin** (any user)

Displays a profile embed for a tester:
- Display name
- Discord username
- Registration date
- Total bugs reported / resolved
- Total suggestions submitted / implemented
- Total earned all-time
- Weeks active
- Senior Tester status

When a Tester runs it without mentioning someone, it shows their own profile. Admins can mention any user to view theirs. GCash number is **never shown** in this command — only visible via `/payout gcash`.

---

## `/tester list`
**🟡 Admin**

Displays a paginated embed listing all registered testers:
- Display name
- Discord username
- Active / Inactive status
- Weeks active count

---

## `/tester deactivate @user`
**🔴 Owner Only**

Marks a tester as inactive. Their Tester role is removed, and all bot commands are blocked for them. Their past data is preserved. Bot DMs the user notifying them.

---

## `/tester reactivate @user`
**🔴 Owner Only**

Restores a deactivated tester — re-assigns their Tester role and reactivates their account.

---

---

# PART 2 — BUG REPORTING SYSTEM

---

## `/bug`
**🟢 Tester**

Opens the bug reporting flow.

---

### Guard Checks (run before the modal opens)

Bot checks in this order and returns an ephemeral error if any fail:
1. Is the user registered? (Tester role check)
2. Have they hit their **daily bug limit** (default: 3)?
3. Have they hit their **weekly payout cap** (₱250)?

If all checks pass, the modal opens.

---

### Step 1 — Bug Report Modal

| Field | Type | Required | Notes |
|---|---|---|---|
| Bug Title | Short text | ✅ | Kept concise; used for duplicate detection |
| Steps to Reproduce | Long text | ✅ | Numbered steps |
| What Happened | Long text | ✅ | Actual behavior |
| What Was Expected | Long text | ✅ | Expected behavior |
| Severity | Dropdown (outside modal) | ✅ | Low / Medium / High — selected before modal via a Select Menu |

> **Note:** Severity is collected via a Select Menu sent as an ephemeral message *before* the modal opens, because dropdowns cannot exist inside modals. The modal opens as a response to the severity selection.

---

### Step 2 — Duplicate Detection

On submit, bot runs a **simple string similarity check** on the Bug Title against all existing open bugs.

- If a similar title is found (≥70% match): Bot sends an ephemeral warning embed listing the potential duplicate(s) with two buttons:
  - **✅ This is different, submit anyway**
  - **❌ Cancel, it's a duplicate**
- If no duplicates: Proceeds immediately

If two testers submit the same bug, **only the first reporter receives credit**. The second reporter's submission is flagged as a duplicate and they are notified via ephemeral message. Their submission is still logged but marked `DUPLICATE` with a reference to the original Bug ID.

---

### Step 3 — Submission Output

On successful submission:

- Bot assigns a sequential **Bug ID** (e.g. `BUG-001`)
- Bot posts a formatted embed in `#bug-reports`:

```
🐛 BUG-001 — [Bug Title]
Reported by: @Username
Severity: 🔴 High
Status: 🟡 Open
Date: YYYY-MM-DD HH:MM PHT

Steps to Reproduce:
1. ...

What Happened:
...

What Was Expected:
...
```

- Bot creates a **public thread** on that embed, named `BUG-001 — [Bug Title]`
- Bot sends the first message in the thread:
  > *"📎 Please attach any screenshots, screen recordings, or additional files here. This thread is also where discussion about this bug will happen."*
- Bot sends the reporter a **DM confirmation** embed:
  - Bug ID, title, severity
  - Direct link to the thread
  - Earnings credited: *"+₱15 added to your weekly earnings"*
- Bot logs the submission in `#bot-logs`
- Bot adds **+₱15** to the reporter's weekly earnings in the database

---

## `/bug resolve <bug_id>`
**🔴 Owner Only**

Marks a bug as resolved and triggers the bonus payout.

---

### Flow

1. Bot replies with a **confirmation embed** (ephemeral):
   > *"Mark BUG-001 as resolved? This will credit +₱10 to @Reporter. React to confirm."*
   - **✅ Confirm** | **❌ Cancel**

2. On confirm:
   - Bug status updated to `✅ Resolved` in the database
   - The embed in `#bug-reports` is **edited** to reflect the new status and resolved date
   - The thread is **auto-archived**
   - Bot posts in `#payout-log`:
     > *"✅ BUG-001 resolved! +₱10 bonus credited to @Reporter. Weekly total: ₱XX / ₱250"*
   - Bot **DMs the reporter**:
     > *"Your bug BUG-001 has been marked as resolved! +₱10 bonus added to your earnings."*
   - Bot logs the action in `#bot-logs`

---

## `/bug list [status]`
**🟢 Tester** (view only) | **🟡 Admin** (full list with reporter details)

Displays a paginated embed of all bugs filtered by status.

Status options: `open` | `resolved` | `duplicate` | `all`

Default (no argument): shows `open` bugs only.

---

## `/bug info <bug_id>`
**🟢 Tester**

Displays the full detail embed for a single bug report including all fields, status, reporter, and a link to the thread.

---

## `/bug reopen <bug_id>`
**🔴 Owner Only**

Re-opens a previously resolved bug (e.g. the fix didn't hold). Reverts the status, un-archives the thread, and reverses the ₱10 bonus from the reporter's earnings. Bot DMs the reporter notifying them with the reason.

---

---

# PART 3 — SUGGESTION SYSTEM

---

## `/suggest`
**🟢 Tester**

Opens the suggestion submission flow.

---

### Guard Checks

Bot checks in this order:
1. Is the user registered?
2. Have they hit their **daily suggestion limit** (default: 2)?
3. Have they hit their **weekly payout cap**?

---

### Step 1 — Feature Select Menu

Bot sends an ephemeral message with a **Select Menu dropdown** asking:
> *"Which feature does your suggestion relate to?"*

Options come from the feature list configured during setup (editable via `/config features`). Always includes **Other** as the last option.

---

### Step 2 — Suggestion Modal

Triggered as a response to the feature selection. Opens a modal with:

| Field | Type | Required |
|---|---|---|
| Suggestion Title | Short text | ✅ |
| Description | Long text | ✅ |

---

### Step 3 — Submission Output

On successful submission:

- Bot assigns a sequential **Suggestion ID** (e.g. `SUG-001`)
- Bot posts a formatted embed in `#suggestions`:

```
💡 SUG-001 — [Suggestion Title]
Submitted by: @Username
Feature: Commission System
Status: 🟡 Pending
Date: YYYY-MM-DD HH:MM PHT

Description:
...
```

- Bot sends the submitter a **DM confirmation**:
  - Suggestion ID and title
  - Earnings credited: *"+₱10 added to your weekly earnings"*
- Bot logs in `#bot-logs`
- Bot adds **+₱10** to the submitter's weekly earnings

---

## `/suggestion implement <suggestion_id>`
**🔴 Owner Only**

Marks a suggestion as implemented and triggers the bonus payout.

---

### Flow

1. Bot replies with a **confirmation embed** (ephemeral):
   > *"Mark SUG-001 as implemented? This will credit +₱15 to @Submitter. Confirm?"*
   - **✅ Confirm** | **❌ Cancel**

2. On confirm:
   - Suggestion status updated to `✅ Implemented`
   - Embed in `#suggestions` edited to reflect the new status
   - Bot posts in `#payout-log`:
     > *"✅ SUG-001 implemented! +₱15 bonus credited to @Submitter. Weekly total: ₱XX / ₱250"*
   - Bot **DMs the submitter**
   - Bot logs in `#bot-logs`

---

## `/suggestion dismiss <suggestion_id> [reason]`
**🔴 Owner Only**

Marks a suggestion as dismissed (not going to implement). Updates the embed status and optionally posts the reason. DMs the submitter. No earnings are reversed — the ₱10 submission pay is kept regardless.

---

## `/suggestion list [status]`
**🟢 Tester** | **🟡 Admin**

Paginated embed of suggestions filtered by status: `pending` | `implemented` | `dismissed` | `all`

---

## `/suggestion info <suggestion_id>`
**🟢 Tester**

Full detail embed for a single suggestion.

---

## `/config features`
**🔴 Owner Only**

Opens a modal to update the feature dropdown list for `/suggest`. Enter each feature on a new line. Overwrites the existing list.

---

---

# PART 4 — EARNINGS & PAYOUT SYSTEM

---

## `/earnings [@user]`
**🟢 Tester** (own only) | **🟡 Admin** (any user)

Displays the current week's earnings breakdown as an embed:

```
📊 Weekly Earnings — @Username
Week of: Mon DD MMM – Sun DD MMM

Bugs Reported:       3   → +₱45
Bugs Resolved:       2   → +₱20
Suggestions Submitted: 1 → +₱10
Suggestions Implemented: 0 → +₱0
─────────────────────────────
Total This Week:     ₱75
Cap Remaining:       ₱175 / ₱250
Payout Status:       ⏳ Pending
```

---

## `/leaderboard`
**🟢 Tester**

Displays the top testers for the current week ranked by total earnings. Paginated; shows top 10 per page. Resets every Monday with the payout cycle.

---

## `/payout generate`
**🔴 Owner Only**

Generates the payout summary for the current week. Posts a detailed embed in `#payout-log` listing:
- Every tester with earnings above ₱0
- Their Display Name
- Their GCash number (masked in the public embed: `09XX****XXX`)
- Total earnings

Also posts a **private summary** in `#bot-logs` with unmasked GCash numbers for the owner's reference.

---

## `/payout gcash @user`
**🔴 Owner Only**

Returns the target tester's **unmasked** GCash number as an ephemeral reply (only the owner can see it). Used to retrieve the number before sending payment. Logged in `#bot-logs`.

---

## `/payout confirm @user`
**🔴 Owner Only**

Marks a tester as paid for the current week.

- Payout record updated to `✅ Paid`
- Bot posts in `#payout-log`:
  > *"💸 @Username — ₱XX sent via GCash. Week of MM/DD."*
- Bot **DMs the tester**:
  > *"Your payout of ₱XX has been sent to your GCash (09XX****XXX). Thank you for testing!"*
- Logged in `#bot-logs`

---

## `/payout history [@user]`
**🔴 Owner Only**

Shows a paginated payout history table — all weeks, amounts paid, and dates confirmed. Can filter by user.

---

---

# PART 5 — MILESTONE & RATE MANAGEMENT

---

## `/milestone add`
**🔴 Owner Only**

Opens a modal to define a new milestone:

| Field | Notes |
|---|---|
| Milestone Name | e.g. "v1.0 Stable Release" |
| Description | Short description of what this marks |
| Rate Changes | e.g. "bug_report_rate=30, weekly_cap=350" — comma-separated key=value pairs |

Milestone is saved but **not applied yet** until you run `/milestone reach`.

---

## `/milestone reach <milestone_name>`
**🔴 Owner Only**

Marks a milestone as reached and applies its rate changes immediately.

- Bot posts a milestone announcement embed in `#uat-announcements`:
  > *"🏁 Milestone Reached: v1.0 Stable Release! Bug report rate is now ₱30. Thanks to all testers!"*
- Rates updated in database
- `/rates` command now reflects the new values
- Logged in `#bot-logs`

---

## `/milestone list`
**🟢 Tester**

Shows all milestones — reached and upcoming — in a paginated embed.

---

## `/rates`
**🟢 Tester**

Displays the current earning rates and daily/weekly limits in a clean embed. Anyone can run this at any time.

```
💰 Current Earning Rates

Bug Reported:           +₱15
Bug Resolved (bonus):   +₱10
Suggestion Submitted:   +₱10
Suggestion Implemented: +₱15

Daily Limits:
  Bugs:        3/day
  Suggestions: 2/day

Weekly Cap:    ₱250/week
Payout Day:    Every Monday
```

---

## Loyalty Bonus (Automatic)
**Applied automatically — no command needed**

Every Monday when the weekly reset runs, bot checks if a tester has been **active for 4 or more consecutive weeks** (at least 1 submission in each of those weeks).

If the condition is met:
- **+₱50 loyalty bonus** is added to that week's payout
- Bot posts in `#payout-log`: *"⭐ Loyalty Bonus: @Username has been active for 4 weeks! +₱50 added."*
- Bot DMs the tester notifying them
- Bot assigns the **Senior Tester** role if not already assigned

---

---

# PART 6 — ANNOUNCEMENTS & NOTIFICATIONS

---

## `/patch <notes>`
**🔴 Owner Only**

Posts a patch scope announcement in `#uat-announcements` so testers know where to focus their testing.

Format:
```
🔧 Patch Notes — v[X.X] | [Date]

What changed:
[notes]

Focus areas for testing:
[auto-extracted or manually written by owner]

Happy testing! 🧪
```

Bot also pings the `@Tester` role when this is posted.

---

## Automated Weekly Reminder
**Automatic — no command needed | 🔴 Owner configures time in `/config`**

Every **Sunday at a configured time (default: 8:00 PM PHT)**, bot posts in `#uat-announcements`:
> *"⏰ Payout reminder! Tomorrow is Monday — payouts go out in the morning. Check your earnings with /earnings. Thanks for testing this week!"*

---

## Automated Weekly Reset
**Automatic — every Monday at midnight PHT**

- Daily limits reset for all testers
- Weekly earnings counters reset (previous week's data archived, not deleted)
- Leaderboard resets
- Bot posts in `#uat-announcements`:
  > *"🔄 A new testing week has started! Limits and earnings have been reset. Good luck!"*

---

---

# PART 7 — CONFIG & ADMIN

---

## `/config view`
**🔴 Owner Only**

Displays all current bot settings in one embed:
- All earning rates
- Daily and weekly limits
- Channel mappings
- Role mappings
- Feature dropdown list
- Timezone
- Reminder time

---

## `/config set <key> <value>`
**🔴 Owner Only**

Updates a single config value on the fly. No restart needed.

Available keys:

| Key | Example Value |
|---|---|
| `bug_report_rate` | `15` |
| `bug_resolve_bonus` | `10` |
| `suggestion_submit_rate` | `10` |
| `suggestion_implement_bonus` | `15` |
| `weekly_cap` | `250` |
| `daily_bug_limit` | `3` |
| `daily_suggestion_limit` | `2` |
| `reminder_time` | `20:00` |
| `payout_day` | `Monday` |

---

## `/config features`
**🔴 Owner Only**

*(Also listed under Suggestion System)*

Reopens the feature list modal. Overwrites the current dropdown options for `/suggest`.

---

## `/admin assign-role <role_type> @role`
**🔴 Owner Only**

Re-maps the bot's role references after setup. Role types: `tester` | `senior_tester` | `admin`

---

## `/admin assign-channel <channel_type> #channel`
**🔴 Owner Only**

Re-maps a bot channel reference after setup. Channel types: `bug-reports` | `suggestions` | `payout-log` | `bot-logs` | `announcements` | `register-here` | `guidelines`

---

---

# PART 8 — DATABASE STRUCTURE

> Uses **SQLite** via `aiosqlite`. No external database server needed.

---

### Tables

**`testers`**
| Column | Type | Notes |
|---|---|---|
| user_id | TEXT PK | Discord user ID |
| display_name | TEXT | From registration modal |
| gcash_number | TEXT | Encrypted at rest |
| registered_at | DATETIME | |
| is_active | BOOLEAN | |
| weeks_active | INTEGER | Incremented each Monday if active |
| consecutive_weeks | INTEGER | For loyalty bonus tracking |
| role | TEXT | `tester` or `senior_tester` |

**`bugs`**
| Column | Type | Notes |
|---|---|---|
| bug_id | TEXT PK | e.g. `BUG-001` |
| reporter_id | TEXT FK | References testers.user_id |
| title | TEXT | |
| steps | TEXT | |
| actual | TEXT | |
| expected | TEXT | |
| severity | TEXT | `low` / `medium` / `high` |
| status | TEXT | `open` / `resolved` / `duplicate` |
| duplicate_of | TEXT | Bug ID of original if duplicate |
| submitted_at | DATETIME | |
| resolved_at | DATETIME | |
| thread_id | TEXT | Discord thread ID |

**`suggestions`**
| Column | Type | Notes |
|---|---|---|
| suggestion_id | TEXT PK | e.g. `SUG-001` |
| submitter_id | TEXT FK | References testers.user_id |
| feature_tag | TEXT | From dropdown |
| title | TEXT | |
| description | TEXT | |
| status | TEXT | `pending` / `implemented` / `dismissed` |
| dismiss_reason | TEXT | Optional |
| submitted_at | DATETIME | |
| actioned_at | DATETIME | |

**`earnings`**
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| user_id | TEXT FK | |
| week_start | DATE | Monday of that week |
| bugs_submitted | INTEGER | |
| bugs_resolved | INTEGER | |
| suggestions_submitted | INTEGER | |
| suggestions_implemented | INTEGER | |
| loyalty_bonus | INTEGER | ₱0 or ₱50 |
| total_earned | INTEGER | |
| is_paid | BOOLEAN | |
| paid_at | DATETIME | |

**`config`**
| Column | Type | Notes |
|---|---|---|
| key | TEXT PK | Config key |
| value | TEXT | Config value (cast in code) |

**`milestones`**
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | |
| description | TEXT | |
| rate_changes | TEXT | JSON string |
| reached | BOOLEAN | |
| reached_at | DATETIME | |

---

---

# PART 9 — TECH STACK SUMMARY

| Component | Tool |
|---|---|
| Bot framework | `discord.py` v2.x |
| Slash commands | `discord.app_commands` |
| Modals | `discord.ui.Modal` |
| Buttons & Select Menus | `discord.ui.View` |
| Database | `SQLite` via `aiosqlite` |
| Config storage | `config` table in SQLite (+ `.env` for secrets) |
| GCash number encryption | `cryptography` (Fernet symmetric encryption) |
| Timezone handling | `pytz` (Asia/Manila) |
| Scheduling (resets, reminders) | `discord.ext.tasks` |
| Hosting | Local machine or VPS (e.g. Railway, Render free tier) |

---

*Last updated: April 2026 | Specification v1.0*

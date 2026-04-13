# UAT Tracking Bot — Core Implementation Prompt
### Instruction set for an AI coding assistant (Cursor, Claude Code, etc.)

---

## HOW TO USE THIS PROMPT

Paste the full contents of this file as your first message to your AI coding assistant. It contains everything needed to scaffold and implement the core features of the UAT Tracking Bot. Follow the phases in order — do not skip ahead. Each phase builds on the previous one.

---

---

## CONTEXT & OVERVIEW

You are building a **Discord bot** for tracking UAT (User Acceptance Testing) submissions, earnings, and payouts. The bot is for a small private Discord server where the owner runs a commission Discord bot and pays friends (testers) via GCash to find bugs and submit suggestions.

**Full specification reference:** `UAT_Bot_Features.md` — refer to it at all times for exact flows, field names, embed formats, and behavior rules.

**Tech stack (non-negotiable):**
- `discord.py` v2.x with `app_commands` (slash commands)
- `discord.ui.Modal`, `discord.ui.View`, `discord.ui.Button`, `discord.ui.Select`
- `aiosqlite` for async SQLite database access
- `python-dotenv` for environment variables
- `pytz` for Asia/Manila timezone handling
- `cryptography` (Fernet) for encrypting GCash numbers at rest
- `discord.ext.tasks` for scheduled jobs

**Do not use:**
- Any external database (no PostgreSQL, no MongoDB, no Firebase)
- Any web framework or REST API layer
- Any third-party bot framework wrappers

---

## PROJECT STRUCTURE

Scaffold the project with this exact folder structure before writing any feature code:

```
uat-bot/
├── bot.py                  # Entry point — initializes bot, loads cogs, starts tasks
├── .env                    # BOT_TOKEN, OWNER_ID, FERNET_KEY (never commit this)
├── .env.example            # Template with empty values
├── requirements.txt        # All dependencies
├── database/
│   ├── __init__.py
│   ├── db.py               # DB connection, initialization, and all query functions
│   └── schema.sql          # Full CREATE TABLE statements
├── cogs/
│   ├── __init__.py
│   ├── setup.py            # /setup and /setup reset
│   ├── registration.py     # /register, /update-gcash, /tester group
│   ├── bugs.py             # /bug, /bug resolve, /bug list, /bug info, /bug reopen
│   ├── suggestions.py      # /suggest, /suggestion implement, /suggestion dismiss, /suggestion list, /suggestion info
│   └── earnings.py         # /earnings, /rates
├── ui/
│   ├── __init__.py
│   ├── modals.py           # All Modal subclasses
│   ├── views.py            # All View subclasses (buttons, selects)
│   └── embeds.py           # All embed builder functions
└── utils/
    ├── __init__.py
    ├── checks.py           # Permission check decorators and guard functions
    ├── config.py           # Config read/write helpers (reads from DB config table)
    ├── crypto.py           # Fernet encrypt/decrypt helpers for GCash numbers
    └── time_utils.py       # PHT timezone helpers, week_start calculation
```

Create all files and folders. Empty `__init__.py` files are fine. Populate each file as you implement each phase below.

---

## ENVIRONMENT VARIABLES

`.env` must contain:

```
BOT_TOKEN=your_discord_bot_token_here
OWNER_ID=your_discord_user_id_here
FERNET_KEY=generate_this_with_fernet_generate_key
```

`.env.example`:
```
BOT_TOKEN=
OWNER_ID=
FERNET_KEY=
```

`requirements.txt`:
```
discord.py>=2.3.0
aiosqlite>=0.19.0
python-dotenv>=1.0.0
pytz>=2024.1
cryptography>=42.0.0
```

---

## DATABASE SCHEMA

Implement the full schema in `database/schema.sql`. Use exactly these table definitions — column names and types must match the spec exactly so that all query functions work consistently.

```sql
CREATE TABLE IF NOT EXISTS testers (
    user_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    gcash_number TEXT NOT NULL,
    registered_at DATETIME NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    weeks_active INTEGER NOT NULL DEFAULT 0,
    consecutive_weeks INTEGER NOT NULL DEFAULT 0,
    role TEXT NOT NULL DEFAULT 'tester'
);

CREATE TABLE IF NOT EXISTS bugs (
    bug_id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL,
    title TEXT NOT NULL,
    steps TEXT NOT NULL,
    actual TEXT NOT NULL,
    expected TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    duplicate_of TEXT,
    submitted_at DATETIME NOT NULL,
    resolved_at DATETIME,
    thread_id TEXT,
    FOREIGN KEY (reporter_id) REFERENCES testers(user_id)
);

CREATE TABLE IF NOT EXISTS suggestions (
    suggestion_id TEXT PRIMARY KEY,
    submitter_id TEXT NOT NULL,
    feature_tag TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    dismiss_reason TEXT,
    submitted_at DATETIME NOT NULL,
    actioned_at DATETIME,
    FOREIGN KEY (submitter_id) REFERENCES testers(user_id)
);

CREATE TABLE IF NOT EXISTS earnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    week_start DATE NOT NULL,
    bugs_submitted INTEGER NOT NULL DEFAULT 0,
    bugs_resolved INTEGER NOT NULL DEFAULT 0,
    suggestions_submitted INTEGER NOT NULL DEFAULT 0,
    suggestions_implemented INTEGER NOT NULL DEFAULT 0,
    loyalty_bonus INTEGER NOT NULL DEFAULT 0,
    total_earned INTEGER NOT NULL DEFAULT 0,
    is_paid INTEGER NOT NULL DEFAULT 0,
    paid_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES testers(user_id)
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    rate_changes TEXT NOT NULL,
    reached INTEGER NOT NULL DEFAULT 0,
    reached_at DATETIME
);

CREATE TABLE IF NOT EXISTS daily_counts (
    user_id TEXT NOT NULL,
    date DATE NOT NULL,
    bugs_today INTEGER NOT NULL DEFAULT 0,
    suggestions_today INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, date),
    FOREIGN KEY (user_id) REFERENCES testers(user_id)
);
```

> Note: `daily_counts` is an extra table not listed in the spec but required to track per-day limits cleanly without querying the bugs/suggestions tables on every submission.

In `database/db.py`, implement an `init_db()` async function that:
1. Opens a connection to `uat_bot.db`
2. Reads and executes `schema.sql`
3. Seeds the `config` table with default values if it's empty:

```python
DEFAULT_CONFIG = {
    "bug_report_rate": "15",
    "bug_resolve_bonus": "10",
    "suggestion_submit_rate": "10",
    "suggestion_implement_bonus": "15",
    "weekly_cap": "250",
    "daily_bug_limit": "3",
    "daily_suggestion_limit": "2",
    "reminder_time": "20:00",
    "payout_day": "Monday",
    "feature_list": "Commission System\nBug Tracker\nPayout System\nRegistration\nOther",
    "channel_bug_reports": "",
    "channel_suggestions": "",
    "channel_payout_log": "",
    "channel_bot_logs": "",
    "channel_announcements": "",
    "channel_register_here": "",
    "channel_guidelines": "",
    "role_tester": "",
    "role_admin": "",
    "role_senior_tester": "",
    "setup_complete": "false"
}
```

Also implement these async query helper functions in `db.py` (these will be imported by all cogs):

```python
# Config
async def get_config(key: str) -> str
async def set_config(key: str, value: str) -> None
async def get_all_config() -> dict

# Testers
async def get_tester(user_id: str) -> dict | None
async def create_tester(user_id, display_name, gcash_encrypted, registered_at) -> None
async def update_tester_gcash(user_id: str, gcash_encrypted: str) -> None
async def deactivate_tester(user_id: str) -> None
async def reactivate_tester(user_id: str) -> None
async def get_all_testers(active_only: bool = True) -> list[dict]

# Bugs
async def get_next_bug_id() -> str           # Returns "BUG-001", "BUG-002", etc.
async def create_bug(bug_id, reporter_id, title, steps, actual, expected, severity, submitted_at) -> None
async def get_bug(bug_id: str) -> dict | None
async def update_bug_status(bug_id: str, status: str, resolved_at=None) -> None
async def update_bug_thread(bug_id: str, thread_id: str) -> None
async def get_bugs_by_status(status: str) -> list[dict]
async def get_all_open_bug_titles() -> list[str]   # For duplicate detection

# Suggestions
async def get_next_suggestion_id() -> str    # Returns "SUG-001", etc.
async def create_suggestion(suggestion_id, submitter_id, feature_tag, title, description, submitted_at) -> None
async def get_suggestion(suggestion_id: str) -> dict | None
async def update_suggestion_status(suggestion_id: str, status: str, dismiss_reason=None, actioned_at=None) -> None
async def get_suggestions_by_status(status: str) -> list[dict]

# Earnings
async def get_or_create_earnings(user_id: str, week_start: date) -> dict
async def add_earnings(user_id: str, week_start: date, field: str, amount: int) -> None
async def get_weekly_total(user_id: str, week_start: date) -> int

# Daily counts
async def get_daily_counts(user_id: str, today: date) -> dict
async def increment_daily_count(user_id: str, today: date, field: str) -> None
```

---

---

# PHASE 1 — BOT ENTRY POINT

Implement `bot.py`:

1. Load `.env` with `python-dotenv`
2. Set up `discord.Client` with `intents`:
   - `guilds`, `members`, `message_content` all enabled
3. Use a `commands.Bot` instance with `command_prefix="!"` (prefix won't be used but is required)
4. On `setup_hook`, call `await init_db()` and load all cogs from the `cogs/` directory
5. On `on_ready`, print the bot's username and ID to console
6. Sync the command tree globally on first run using `await bot.tree.sync()`
7. Run the bot with `BOT_TOKEN` from `.env`

---

---

# PHASE 2 — UTILITY LAYERS

Implement these before any cog — all cogs depend on them.

---

### `utils/crypto.py`

```python
# Use cryptography.fernet.Fernet
# FERNET_KEY loaded from .env

def encrypt_gcash(number: str) -> str
    # Returns base64-encoded encrypted string

def decrypt_gcash(encrypted: str) -> str
    # Returns plaintext GCash number

def mask_gcash(number: str) -> str
    # Input: "09123456789"
    # Output: "09XX****789"
    # Always mask digits 3-6 with XX and 5-8 with ****
    # Keep first 2 and last 3 digits visible
```

---

### `utils/time_utils.py`

```python
import pytz
from datetime import datetime, date, timedelta

PHT = pytz.timezone("Asia/Manila")

def now_pht() -> datetime
    # Returns current datetime in PHT

def today_pht() -> date
    # Returns current date in PHT

def get_week_start(d: date = None) -> date
    # Returns the Monday of the current (or given) week
    # Used as the key for all weekly earnings records
```

---

### `utils/checks.py`

Implement these as reusable async functions (not decorators — call them manually at the top of each command handler so you can send custom ephemeral error messages):

```python
async def is_owner(interaction: discord.Interaction) -> bool
    # Checks if interaction.user.id == int(OWNER_ID from .env)

async def is_admin(interaction: discord.Interaction) -> bool
    # Checks if user has the UAT Admin role (read role ID from config)
    # Owner also passes this check

async def is_registered(interaction: discord.Interaction) -> bool
    # Checks if the user has the Tester role (read role ID from config)
    # Also verify they exist in the testers table

async def is_active_tester(interaction: discord.Interaction) -> bool
    # Checks is_registered AND is_active == 1 in DB

async def check_daily_bug_limit(user_id: str, today: date) -> bool
    # Returns True if under limit, False if at/over

async def check_daily_suggestion_limit(user_id: str, today: date) -> bool
    # Returns True if under limit, False if at/over

async def check_weekly_cap(user_id: str, week_start: date) -> bool
    # Returns True if under cap, False if at/over
```

---

### `utils/config.py`

```python
async def get_rate(key: str) -> int
    # Thin wrapper: reads from config table, casts to int

async def get_channel(bot, key: str) -> discord.TextChannel | None
    # Reads channel ID from config, fetches and returns the channel object
    # key examples: "channel_bug_reports", "channel_bot_logs"

async def get_role(guild, key: str) -> discord.Role | None
    # Reads role ID from config, returns role object
    # key examples: "role_tester", "role_admin"

async def get_feature_list() -> list[str]
    # Reads "feature_list" from config
    # Splits on newline
    # Returns as a list of strings
```

---

### `ui/embeds.py`

Build all embed factory functions here. Every embed must use consistent colors:

| Embed Type | Color |
|---|---|
| Success / Confirmation | `0x57F287` (green) |
| Error / Warning | `0xED4245` (red) |
| Info / Neutral | `0x5865F2` (blurple) |
| Bug report | `0xFEE75C` (yellow) |
| Suggestion | `0x57F287` (green) |
| Payout | `0xEB459E` (pink) |
| Announcement | `0x5865F2` (blurple) |

Implement these embed builders (return `discord.Embed`, do not send):

```python
def tos_embed() -> discord.Embed
def registration_success_embed(display_name, masked_gcash, rates: dict, channels: dict) -> discord.Embed
def tester_profile_embed(tester: dict, all_time_stats: dict) -> discord.Embed
def bug_report_embed(bug: dict, reporter: discord.User) -> discord.Embed
def suggestion_embed(suggestion: dict, submitter: discord.User) -> discord.Embed
def earnings_embed(tester: dict, earnings: dict, cap: int) -> discord.Embed
def rates_embed(config: dict) -> discord.Embed
def error_embed(message: str) -> discord.Embed
def success_embed(message: str) -> discord.Embed
def confirmation_embed(title: str, description: str) -> discord.Embed
def bot_log_embed(action: str, details: dict) -> discord.Embed
```

---

---

# PHASE 3 — SETUP WIZARD

**File:** `cogs/setup.py`

Implement `/setup` following Part 0 of the spec exactly.

**Key implementation notes:**

- The wizard is stateful — use a Python dict keyed by `interaction.user.id` to store wizard progress in memory (not DB). It only needs to live for the duration of one setup session.
- Each step sends a new ephemeral message with buttons (Next/Skip/Cancel or specific choice buttons).
- "Next" advances the step counter. "Cancel" clears state and sends a cancelled message. "Start Over" resets state to step 1.
- The wizard state dict should hold: `{ step: int, roles: dict, channels: dict, rates: dict, features: list }`

**Step sequence:**

```
Step 1: Role setup
  → Bot checks if UAT Admin, Tester, Senior Tester roles exist
  → If not: show "Create New" / "Use Existing" buttons
  → Create New: bot creates roles with correct colors, saves IDs to config
  → Use Existing: bot asks user to mention the 3 roles one by one (3 separate prompts using a text-based follow-up — use a modal with 3 fields for this)

Step 2: Channel setup  
  → Same pattern as Step 1 but for all 7 channels
  → Create New: bot creates a category "📋 UAT Testing" then all 7 channels inside it
    - #bot-logs: set permissions so only Owner and UAT Admin can view it
    - #tester-guidelines: set permissions so Tester role can read but not send messages
  → Use Existing: bot sends a modal with 7 fields asking for channel mentions

Step 3: Rate configuration
  → Bot sends an embed showing default rates with an "Edit Rates" button
  → Button opens a Modal with 7 fields pre-filled with defaults (modal fields cannot be pre-filled natively — just show placeholders with the default values)
  → On submit: validate all values are positive integers, save to config

Step 4: Feature dropdown list
  → Bot sends current default list and an "Edit Features" button
  → Button opens a Modal with a single long-text field
  → On submit: split on newlines, trim whitespace, save to config as newline-joined string
  → Always enforce that "Other" is appended to the end if not already present

Step 5: Milestone configuration
  → Show "Add Milestone Now" / "Skip for Now" buttons
  → Skip: proceed to Step 6
  → Add Milestone: open a modal (Milestone Name, Description, Rate Changes)
  → After submit, ask "Add another?" with Yes/No buttons
  → Save each to milestones table with reached=0

Step 6: Summary and confirmation
  → Build a summary embed showing all configured values
  → Show "✅ Confirm Setup" / "🔄 Start Over" buttons
  → Confirm: 
    - Set config key "setup_complete" = "true"
    - Post tester guidelines embed in #tester-guidelines and pin it
    - Clear wizard state for this user
    - Send final success message
  → Start Over: reset wizard state to step 1, re-run step 1
```

**Guard:** Before running any step beyond Step 1, check that `setup_complete != "true"`. If setup is already done, reply with: *"Setup has already been completed. Use `/config set` to change individual settings."*

**`/setup reset`:**
- Check is_owner
- Send confirmation embed with "✅ Confirm Reset" / "❌ Cancel" buttons
- On confirm: delete and recreate all tables (call `init_db()` fresh), set `setup_complete = "false"`, re-run setup wizard

---

---

# PHASE 4 — REGISTRATION SYSTEM

**File:** `cogs/registration.py`

Implement following Part 1 of the spec exactly.

---

### `/register`

**Guard:** Command can only be used in the channel stored in `config["channel_register_here"]`. If used elsewhere, reply ephemeral: *"Please head to #register-here to register."*

**Guard:** If `setup_complete != "true"`, reply ephemeral: *"The bot hasn't been set up yet. Ask the owner to run /setup first."*

**Flow:**

```
1. Check if already registered (get_tester by user_id)
   → If yes: ephemeral error "You're already registered. Use /update-gcash to change your GCash number."

2. Send ephemeral TOS embed (use tos_embed() from embeds.py)
   Attach a View with two buttons:
   - ✅ "I Accept" (style: success, custom_id: "tos_accept")
   - ❌ "I Decline" (style: danger, custom_id: "tos_decline")

3. On "I Decline":
   - Edit the message: "Registration cancelled. Come back when you're ready!"
   - Disable both buttons

4. On "I Accept":
   - Open RegistrationModal (see below)

5. On modal submit:
   - Validate GCash: must match regex r"^09\d{9}$"
   - If invalid: reply ephemeral error, do NOT close the modal flow — tell them to run /register again
   - If valid:
     a. Encrypt GCash with encrypt_gcash()
     b. Insert into testers table via create_tester()
     c. Assign Tester role (read role ID from config)
     d. Create earnings row for current week via get_or_create_earnings()
     e. Reply ephemeral: "You're registered! Check your DMs."
     f. DM user with registration_success_embed()
     g. Log to #bot-logs with bot_log_embed("REGISTRATION", {user_id, display_name, timestamp})
```

**`RegistrationModal`** (in `ui/modals.py`):
- Title: "Tester Registration"
- Field 1: `display_name` — label "Display Name", placeholder "What should we call you?", max_length=50, required=True
- Field 2: `gcash_number` — label "GCash Mobile Number", placeholder "09XXXXXXXXX", max_length=11, min_length=11, required=True

---

### `/update-gcash`

**Guard:** Check is_active_tester.

- Open `UpdateGCashModal` — single field: "New GCash Number", same validation as registration
- On submit:
  - Validate format
  - Encrypt and update in DB
  - DM user confirmation with new masked number
  - Log to #bot-logs

---

### `/tester info [@user]`

**Guard:**
- If no user mentioned: must be is_active_tester → shows own profile
- If user mentioned: must be is_admin → shows that user's profile

**Logic:**
- Fetch tester row from DB
- Aggregate all-time stats:
  - Total bugs submitted: `COUNT(*)` from bugs where `reporter_id = user_id`
  - Total bugs resolved: `COUNT(*)` from bugs where `reporter_id = user_id AND status = "resolved"`
  - Total suggestions submitted: `COUNT(*)` from suggestions where `submitter_id = user_id`
  - Total suggestions implemented: `COUNT(*)` from suggestions where `submitter_id = user_id AND status = "implemented"`
  - Total earned all-time: `SUM(total_earned)` from earnings where `user_id = user_id`
- Send tester_profile_embed()
- GCash number is NEVER shown in this command

---

### `/tester list`

**Guard:** is_admin

- Fetch all testers from DB
- Build paginated embeds (5 testers per page)
- Use a View with ⬅️ / ➡️ buttons to navigate pages
- Each entry shows: Display Name, Discord username (fetched via `bot.fetch_user()`), Active status (✅/❌), Weeks active

---

### `/tester deactivate @user`

**Guard:** is_owner

- Fetch tester, confirm they exist and are active
- Send confirmation embed with ✅/❌ buttons
- On confirm:
  - Call deactivate_tester()
  - Remove Tester role from user
  - DM user: *"Your tester account has been deactivated. Contact the owner if you think this is a mistake."*
  - Log to #bot-logs

---

### `/tester reactivate @user`

**Guard:** is_owner

- Fetch tester, confirm they exist and are inactive
- Call reactivate_tester()
- Re-assign Tester role
- DM user: *"Your tester account has been reactivated! Welcome back."*
- Log to #bot-logs

---

---

# PHASE 5 — BUG REPORTING SYSTEM

**File:** `cogs/bugs.py`

Implement following Part 2 of the spec exactly.

---

### `/bug`

**Guard sequence (run in order, stop at first failure):**
```
1. is_active_tester → "You need to register first. Head to #register-here."
2. check_daily_bug_limit → "You've hit today's bug limit (3/day). Come back tomorrow!"
3. check_weekly_cap → "You've reached the weekly earnings cap (₱250). See you next week!"
```

**Flow:**

```
Step 1: Severity Select Menu
  → Send ephemeral message with a discord.ui.Select dropdown:
    Placeholder: "Select severity level"
    Options:
      - "🔴 High — Core functionality broken"  value="high"
      - "🟡 Medium — Feature partially broken"  value="medium"
      - "🟢 Low — Minor issue or cosmetic"      value="low"
  → On selection: store severity in the view's state, then open BugReportModal

Step 2: BugReportModal
  Fields:
    - bug_title: label="Bug Title", placeholder="Short, clear title", max_length=100, required=True
    - steps: label="Steps to Reproduce", style=TextStyle.paragraph, placeholder="1. Do this\n2. Then this\n3. Then this", required=True
    - actual: label="What Happened", style=TextStyle.paragraph, placeholder="Describe what actually happened", required=True
    - expected: label="What Was Expected", style=TextStyle.paragraph, placeholder="Describe what should have happened", required=True

Step 3: Duplicate detection (on modal submit)
  → Fetch all open bug titles via get_all_open_bug_titles()
  → For each title, compute similarity score:
    Use this simple approach (no external libraries):
      - Lowercase both strings
      - Split into word sets
      - similarity = len(intersection) / len(union)   (Jaccard similarity)
  → If any title scores >= 0.7:
    Send ephemeral embed listing potential duplicates with two buttons:
      - ✅ "This is different, submit anyway"
      - ❌ "Cancel, it's a duplicate"
    On cancel: interaction ends
    On confirm: proceed to Step 4

Step 4: Submission
  → get_next_bug_id() — query MAX(bug_id) from bugs, parse number, increment
  → Insert into bugs table via create_bug()
  → Post bug_report_embed() in #bug-reports channel
  → Create a public thread on that message:
      name = f"{bug_id} — {bug_title}" (truncate title to 80 chars if needed)
  → Send first message in thread:
      "📎 **Attach your evidence here.**\nScreenshots, screen recordings, or any other files that help reproduce this bug. This thread is also where any discussion about this bug happens."
  → Update bug's thread_id in DB via update_bug_thread()
  → Credit submission earnings:
      - add_earnings(user_id, week_start, "bugs_submitted", 1)
      - add_earnings(user_id, week_start, "total_earned", bug_report_rate)
  → Increment daily bug count: increment_daily_count(user_id, today, "bugs_today")
  → DM reporter:
      Embed with: Bug ID, title, severity, link to thread, "+₱{rate} added to your weekly earnings"
  → Reply ephemeral to original interaction: "Bug {bug_id} submitted! Check your DMs for the thread link."
  → Log to #bot-logs
```

---

### `/bug resolve <bug_id>`

**Guard:** is_owner

```
1. Fetch bug, confirm it exists and status == "open"
   → If not found: ephemeral error "Bug ID not found."
   → If already resolved: ephemeral error "This bug is already resolved."

2. Send ephemeral confirmation embed:
   "Mark {bug_id} as resolved? This will credit +₱{bonus} to {reporter_display_name}."
   Buttons: ✅ Confirm | ❌ Cancel

3. On confirm:
   → update_bug_status(bug_id, "resolved", resolved_at=now_pht())
   → Edit the bug embed in #bug-reports:
       Update Status field to "✅ Resolved"
       Add "Resolved At" field with timestamp
   → Archive the thread (thread.edit(archived=True))
   → Credit bonus earnings to reporter:
       add_earnings(reporter_id, week_start, "bugs_resolved", 1)
       add_earnings(reporter_id, week_start, "total_earned", bug_resolve_bonus)
   → Post in #payout-log:
       "✅ {bug_id} resolved! +₱{bonus} bonus credited to {display_name}. Weekly total: ₱{total} / ₱{cap}"
   → DM reporter:
       "Your bug {bug_id} has been marked as resolved! +₱{bonus} bonus added to your earnings. 🎉"
   → Log to #bot-logs
```

---

### `/bug list [status]`

**Guard:** is_active_tester (view only — no admin distinction needed for list)

- `status` parameter: choices are `open`, `resolved`, `duplicate`, `all` — default `open`
- Fetch matching bugs from DB
- Display 5 per page in paginated embeds with ⬅️ / ➡️ buttons
- Each entry: Bug ID, Title, Severity, Reporter display name, Submitted date

---

### `/bug info <bug_id>`

**Guard:** is_active_tester

- Fetch bug from DB
- Send full bug_report_embed() as ephemeral (or public — your choice, ephemeral is cleaner)
- Include thread link if available

---

### `/bug reopen <bug_id>`

**Guard:** is_owner

```
1. Fetch bug, confirm status == "resolved"
2. Send confirmation embed with reason field (use a modal):
   Modal field: "Reason for reopening" (optional, long text)
3. On confirm:
   → update_bug_status(bug_id, "open", resolved_at=None)
   → Unarchive thread (thread.edit(archived=False))
   → Edit bug embed in #bug-reports to revert status to "🟡 Open"
   → Reverse the ₱10 bonus:
       add_earnings(reporter_id, week_start, "bugs_resolved", -1)
       add_earnings(reporter_id, week_start, "total_earned", -bug_resolve_bonus)
   → DM reporter with reason if provided
   → Log to #bot-logs
```

---

---

# PHASE 6 — SUGGESTION SYSTEM

**File:** `cogs/suggestions.py`

Implement following Part 3 of the spec exactly.

---

### `/suggest`

**Guard sequence:**
```
1. is_active_tester
2. check_daily_suggestion_limit → "You've hit today's suggestion limit (2/day). Come back tomorrow!"
3. check_weekly_cap → "You've reached the weekly earnings cap."
```

**Flow:**

```
Step 1: Feature Select Menu
  → Read feature list from config via get_feature_list()
  → Build discord.ui.Select with one option per feature
  → Always ensure "Other" is an option
  → Placeholder: "Which feature does this relate to?"
  → On selection: store feature_tag in view state, open SuggestionModal

Step 2: SuggestionModal
  Fields:
    - title: label="Suggestion Title", placeholder="Short, clear title", max_length=100, required=True
    - description: label="Description", style=TextStyle.paragraph, placeholder="Describe your suggestion in detail", required=True

Step 3: Submission (on modal submit)
  → get_next_suggestion_id()
  → create_suggestion() in DB
  → Post suggestion_embed() in #suggestions channel
  → Credit submission earnings:
      add_earnings(user_id, week_start, "suggestions_submitted", 1)
      add_earnings(user_id, week_start, "total_earned", suggestion_submit_rate)
  → increment_daily_count(user_id, today, "suggestions_today")
  → DM submitter: Suggestion ID, title, feature tag, "+₱{rate} added to earnings"
  → Reply ephemeral: "Suggestion {suggestion_id} submitted! Check your DMs."
  → Log to #bot-logs
```

---

### `/suggestion implement <suggestion_id>`

**Guard:** is_owner

```
1. Fetch suggestion, confirm status == "pending"
2. Send ephemeral confirmation embed with ✅ Confirm | ❌ Cancel
3. On confirm:
   → update_suggestion_status(suggestion_id, "implemented", actioned_at=now_pht())
   → Edit suggestion embed in #suggestions to show "✅ Implemented"
   → Credit bonus earnings to submitter:
       add_earnings(submitter_id, week_start, "suggestions_implemented", 1)
       add_earnings(submitter_id, week_start, "total_earned", suggestion_implement_bonus)
   → Post in #payout-log:
       "✅ {suggestion_id} implemented! +₱{bonus} credited to {display_name}. Weekly total: ₱{total} / ₱{cap}"
   → DM submitter with congratulations and bonus amount
   → Log to #bot-logs
```

---

### `/suggestion dismiss <suggestion_id> [reason]`

**Guard:** is_owner

```
1. Fetch suggestion, confirm status == "pending"
2. Open modal with optional "Reason for dismissal" field
3. On submit:
   → update_suggestion_status(suggestion_id, "dismissed", dismiss_reason=reason, actioned_at=now_pht())
   → Edit suggestion embed in #suggestions to show "❌ Dismissed" (+ reason if provided)
   → DM submitter: "Your suggestion {suggestion_id} has been dismissed. Reason: {reason or 'No reason provided'}. The ₱{rate} submission pay is yours to keep!"
   → Log to #bot-logs
   → NOTE: Do NOT reverse submission earnings — spec states they keep the ₱10
```

---

### `/suggestion list [status]`

**Guard:** is_active_tester

- `status`: `pending`, `implemented`, `dismissed`, `all` — default `pending`
- Paginated, 5 per page, ⬅️ / ➡️ buttons
- Each entry: Suggestion ID, Title, Feature tag, Submitter display name, Submitted date

---

### `/suggestion info <suggestion_id>`

**Guard:** is_active_tester

- Full suggestion_embed() for the given ID, sent ephemeral

---

---

# PHASE 7 — EARNINGS & RATES

**File:** `cogs/earnings.py`

Implement following Part 4 (partial) and Part 5 (rates only) of the spec.

---

### `/earnings [@user]`

**Guard:**
- No user mentioned: is_active_tester (shows own earnings)
- User mentioned: is_admin (shows that user's earnings)

```
1. Determine target user_id
2. Fetch tester from DB
3. Fetch current week's earnings row via get_or_create_earnings(user_id, week_start)
4. Fetch weekly cap from config
5. Build and send earnings_embed():
   Show:
   - Bugs reported + earnings from that
   - Bugs resolved (bonus) + earnings from that
   - Suggestions submitted + earnings
   - Suggestions implemented + earnings
   - Total earned this week
   - Cap remaining (cap - total_earned)
   - Payout status (✅ Paid / ⏳ Pending)
```

---

### `/rates`

**Guard:** is_active_tester (or even no guard — anyone can view)

- Fetch all rate-related config keys
- Send rates_embed() with full breakdown:
  - All earning rates
  - Daily limits
  - Weekly cap
  - Payout day

---

---

# TESTING CHECKLIST

After implementing each phase, test the following manually in a test Discord server:

**Phase 2 (Utils):**
- [ ] Fernet encrypt/decrypt round-trips correctly
- [ ] `mask_gcash("09123456789")` returns `"09XX****789"`
- [ ] `get_week_start()` returns the correct Monday

**Phase 3 (Setup):**
- [ ] `/setup` only works for owner
- [ ] All 6 steps complete without errors
- [ ] Roles and channels are created with correct permissions
- [ ] Config table is populated after completion
- [ ] `/setup reset` asks for confirmation before wiping data

**Phase 4 (Registration):**
- [ ] `/register` in wrong channel shows ephemeral error
- [ ] TOS shows with both buttons
- [ ] Declining ends the flow cleanly
- [ ] Accepting opens the modal
- [ ] Invalid GCash (e.g. "1234") shows a validation error
- [ ] Valid submission assigns Tester role and sends DM
- [ ] Running `/register` again shows "already registered" error
- [ ] `/update-gcash` updates the encrypted value in DB

**Phase 5 (Bugs):**
- [ ] Unregistered user can't run `/bug`
- [ ] Daily limit blocks submission after 3 bugs
- [ ] Severity select appears before modal
- [ ] Modal opens after severity is selected
- [ ] Duplicate detection warning appears for similar titles
- [ ] Bug embed posted in #bug-reports with correct fields
- [ ] Thread created on the embed and named correctly
- [ ] Thread first message asks for attachments
- [ ] Reporter receives DM with thread link
- [ ] Earnings incremented correctly in DB
- [ ] `/bug resolve` asks for confirmation
- [ ] On resolve: embed updated, thread archived, bonus credited, DM sent, payout-log posted

**Phase 6 (Suggestions):**
- [ ] Daily limit blocks after 2 suggestions
- [ ] Feature dropdown shows all configured features
- [ ] Modal opens after feature selected
- [ ] Suggestion embed posted in #suggestions
- [ ] Submitter receives DM with earnings confirmation
- [ ] `/suggestion implement` — same confirm flow as bug resolve
- [ ] `/suggestion dismiss` — DM sent, earnings NOT reversed

**Phase 7 (Earnings):**
- [ ] `/earnings` shows correct breakdown matching DB values
- [ ] `/earnings @user` only works for admins
- [ ] `/rates` shows current config values

---

## IMPORTANT NOTES FOR THE IMPLEMENTOR

1. **Never store plaintext GCash numbers.** Always encrypt before inserting, always decrypt only when displaying to the owner via `/payout gcash`. Mask everywhere else.

2. **All interactions must be responded to within 3 seconds** or Discord will show "This interaction failed." For any operation that takes time (DB writes, DMs), call `await interaction.response.defer(ephemeral=True)` first, then use `await interaction.followup.send(...)` to send the result.

3. **Ephemeral messages cannot be edited after the interaction token expires (15 minutes).** For persistent UI (like bug embeds), send them as regular (non-ephemeral) messages in the target channel.

4. **Views time out after 180 seconds by default.** For confirmation buttons (resolve, dismiss, etc.), set `timeout=60`. For paginated lists, set `timeout=120`. Always disable buttons on timeout by overriding `on_timeout`.

5. **Thread creation requires the bot to have `Create Public Threads` and `Send Messages in Threads` permissions** in `#bug-reports`. Make sure the setup step grants these.

6. **The `week_start` date key must be consistent across all earnings operations.** Always use `get_week_start(today_pht())` — never use raw `datetime.now()`.

7. **Keep all user-facing text consistent with the spec wording.** Error messages, DM content, and embed field names should match what's written in `UAT_Bot_Features.md` wherever specified.

8. **Log everything to #bot-logs** — every registration, bug submission, resolution, suggestion, payout confirmation, and config change. Use `bot_log_embed()` consistently.

9. **Do not implement payout commands (`/payout generate`, `/payout confirm`, `/payout gcash`, `/payout history`) or the leaderboard, milestone commands, or automated tasks in this phase.** Those are secondary features. Focus only on Phases 1–7 above.

10. **When in doubt about behavior, refer to `UAT_Bot_Features.md` first**, then use your best judgment to fill in any gaps not covered by the spec.

---

*Implementation prompt v1.0 — covers core features (Parts 0–4 partial, Part 5 rates only)*
*Secondary features (full payout system, leaderboard, milestones, automation) to be implemented in Phase 2*

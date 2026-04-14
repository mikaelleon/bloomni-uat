# Suggestion System

Covers `/suggest`, `/suggestion list`, `/suggestion info`, `/suggestion acknowledge`, `/suggestion implement`, `/suggestion dismiss`.

## Status values

| Status | Meaning |
|--------|---------|
| `submitted` | Awaiting owner acknowledgement (no submit pay yet). |
| `acknowledged` | Acknowledged; submit rate paid. Can be implemented or dismissed. |
| `implemented` | Implement bonus paid. |
| `dismissed` | Closed without implementation. |

## `/suggest` submit flow

### Guards

1. Active tester.
2. Daily suggestion limit.
3. Weekly cap is enforced when **acknowledging** (owner action).

### Interaction flow

1. Feature select (from config feature list + Other).
2. Modal: title, description.
3. On submit:
   - Next `SUG-xxx` ID, status **`submitted`**.
   - Embed in suggestions channel.
   - Daily counter incremented.
   - **No** earnings on submit — DM embed states it is waiting for **acknowledgement**.

## Owner moderation

### `/suggestion acknowledge` (owner)

- Only **`submitted`** → **`acknowledged`**.
- Pays **suggestion submit rate**; increments `suggestions_acknowledged`.
- Submitter DM: **embed** + **Current stats** (weekly balance, cap remaining, daily slots).

### `/suggestion implement` (owner)

- Status must be **`submitted` or `acknowledged`** (implement bonus is separate from acknowledge pay; typical path is acknowledge then implement).
- Confirmation view; on confirm: **`implemented`**, implement bonus paid, payout log, **embed** DM with stats.

### `/suggestion dismiss` (owner)

- **`submitted` or `acknowledged`** → **`dismissed`**.
- Modal for optional reason; embed updated; submitter DM (plain text with reason in current code).

## Read commands

### `/suggestion list`

- Filters: `submitted`, `acknowledged`, `implemented`, `dismissed`, `all`.
- Paginated.

### `/suggestion info`

- Full suggestion embed for one ID.

## Typical messages

- “Pick a feature, then describe your suggestion.”
- Submit DM: waiting for **acknowledgement** (not “+₱X added” on submit).
- Implement/dismiss copy as in bot responses.

## Feature list

- Edited in **`/setup` Step 4 — Features** (modal: one feature per line). Stored in config as `feature_list`. The wizard keeps **`Other`** available for testers.

# Bug Reporting and Resolution

Covers `/bug`, `/bugs submit`, `/bugs list`, `/bugs info`, `/bugs validate`, `/bugs reject`, `/bugs resolve`, `/bugs reopen`.

## Submission commands

- `/bug`
- `/bugs submit`

Both start the same workflow.

## Status values

| Status | Meaning |
|--------|---------|
| `submitted` | Awaiting owner validation (no report pay yet). |
| `validated` | Validated; report rate paid. Can be resolved or rejected. |
| `rejected` | Not accepted (no pay for validate path). |
| `resolved` | Fix confirmed; resolve bonus paid (from `validated` only). |
| `duplicate` | Linked to another bug via `duplicate_of`. |

`/bugs list` filter **`open`** means **submitted or validated** (unresolved work in progress).

## Submit workflow

### Guards

1. Active tester.
2. Daily bug limit (from config).
3. Weekly cap check applies when validating (not at submit in the same way—owner validates and pay runs then).

### Interaction flow

1. Severity select (High / Medium / Low).
2. Bug modal: title, steps, actual, expected.
3. Duplicate check on title (Jaccard ≥ 0.7 vs “open” titles); user can confirm or cancel.
4. On submit:
   - Next `BUG-xxx` ID.
   - Row saved with status **`submitted`**.
   - Embed in bug reports channel; evidence thread created.
   - Daily `bugs_today` incremented.
   - **No** earnings on submit — DM says it is waiting for **validation**.

## Owner actions

### `/bugs validate` (owner)

- Defers immediately (avoids unknown interaction / timeout).
- Only **`submitted`** → **`validated`**.
- Pays **bug report rate**; increments `bugs_validated`; updates embed.
- Reporter DM: **embed** with title/description plus **Current stats** (weekly balance vs cap, weekly cap remaining, daily bug/suggestion slots left).

### `/bugs reject` (owner)

- **`submitted` or `validated`** → **`rejected`**.
- Embed updated; reporter DM (plain message with reason in current code).

### `/bugs resolve` (owner)

- Bug must be **`validated`** (not merely submitted).
- Confirm/cancel view.
- On confirm: **`resolved`**, thread archived, **resolve bonus** paid, `bugs_resolved` incremented, payout log line, reporter **embed** DM with same stats block as validate.

### `/bugs reopen` (owner)

- From **`resolved`** only.
- Modal optional reason.
- Status → **`validated`** (not back to submitted); resolve bonus reversed in earnings; thread unarchived; reporter notified.

## Read commands

### `/bugs list`

- Active tester; status filter includes `open`, `submitted`, `validated`, `rejected`, `resolved`, `duplicate`, `all`.
- Paginated (5 per page).
- Timestamps shown as simple local-style strings, e.g. **`14 Apr 2026 03:45 PM`** (`_simple_dt`).

### `/bugs info`

- Full `bug_report_embed`; thread link appended when available.

## Tester removal and IDs

When a tester is **deactivated** or **unregistered**, their bug rows are removed and remaining bug IDs are **compacted** globally (`BUG-001` … in submission order). Threads are archived and channel messages removed when the bot can access them.

## Logging

- Events such as `BUG_SUBMIT`, `BUG_RESOLVE`, `BUG_REOPEN`, validate/reject flows are logged via `log_event` when the bot log channel is configured.

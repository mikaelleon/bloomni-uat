# Bug Reporting and Resolution

Covers `/bug`, `/bugs submit`, `/bugs list`, `/bugs info`, `/bugs resolve`, `/bugs reopen`.

## Submission Commands

- `/bug`
- `/bugs submit`

Both trigger the same submit workflow.

## Submit Workflow Logic

### Guard order

1. User must be an active tester.
2. Daily bug limit must not be reached.
3. Weekly cap must not be reached for current bug rate.

### Interaction flow

1. Severity select shown (High/Medium/Low).
2. Bug modal opens with:
   - title
   - steps to reproduce
   - actual result
   - expected result
3. Duplicate check compares title with open bugs using Jaccard similarity.
4. If likely duplicate, bot asks user to continue or cancel.
5. On submit:
   - next bug ID generated (`BUG-001`, etc.)
   - row saved in DB
   - embed posted in bug reports channel
   - public thread created for evidence
   - earnings and daily count updated
   - user DM confirmation sent
   - bot log entry sent

## Owner Actions

### `/bugs resolve`

- Owner only.
- Validates bug exists and is open.
- Confirmation buttons (confirm/cancel).
- On confirm:
  - status -> resolved
  - bug embed edited
  - thread archived
  - resolve bonus added
  - payout log posted
  - reporter DM sent
  - bot log entry sent

### `/bugs reopen`

- Owner only.
- Validates bug is resolved.
- Modal for optional reason.
- On confirm:
  - status -> open
  - bug embed edited
  - thread unarchived
  - resolve bonus reversed
  - reporter DM sent
  - bot log entry sent

## Read Commands

### `/bugs list`

- Active tester required.
- Status filter: open/resolved/duplicate/all
- Paginated response, 5 per page.

### `/bugs info`

- Active tester required.
- Shows full bug embed and thread link when available.

## Output Text Examples

- "Choose severity, then fill out the bug form."
- "You've hit today's bug limit (3/day). Come back tomorrow!"
- "Bug {bug_id} submitted! Check your DMs for the thread link."

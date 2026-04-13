# Suggestion System

Covers `/suggest`, `/suggestion list`, `/suggestion info`, `/suggestion implement`, `/suggestion dismiss`.

## `/suggest` Submit Flow

### Guard order

1. User must be active tester.
2. Daily suggestion limit must not be reached.
3. Weekly cap must not be reached for suggestion submit rate.

### Interaction flow

1. Feature dropdown shown (from config list, includes `Other`).
2. Suggestion modal opens with:
   - title
   - description
3. On submit:
   - next suggestion ID generated (`SUG-001`, etc.)
   - row inserted with pending status
   - embed posted in suggestions channel
   - earnings updated
   - daily counter incremented
   - user DM confirmation sent
   - bot log entry sent

## Owner Moderation

### `/suggestion implement`

- Owner only.
- Suggestion must be pending.
- Confirmation view shown.
- On confirm:
  - status -> implemented
  - embed edited
  - implement bonus credited
  - payout log message sent
  - submitter DM sent
  - bot log entry sent

### `/suggestion dismiss`

- Owner only.
- Suggestion must be pending.
- Modal for optional reason.
- On confirm:
  - status -> dismissed
  - reason stored
  - embed edited
  - submitter DM sent (keeps submission pay)
  - bot log entry sent

## Read Commands

### `/suggestion list`

- Active tester required.
- Filter: pending/implemented/dismissed/all.
- Paginated, 5 rows per page.

### `/suggestion info`

- Active tester required.
- Sends full suggestion embed for selected ID.

## Typical Output Text

- "Pick a feature, then describe your suggestion."
- "Suggestion {id} submitted! Check your DMs."
- "Marked implemented."
- "Dismissed."

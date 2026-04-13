# Registration and Tester Management

Covers `/register`, `/update-gcash`, and `/tester` commands.

## Commands in This Group

- `/register`
- `/update-gcash`
- `/tester info`
- `/tester list`
- `/tester deactivate`
- `/tester reactivate`

## `/register` Flow

### Guards

- Setup must be complete.
- Command must be used in configured register channel.
- User must not already exist in testers table.

### User Experience

1. TOS embed shown with buttons:
   - `I Accept`
   - `I Decline`
2. Accept opens registration modal:
   - Display Name
   - GCash Number
3. GCash format validated: `09XXXXXXXXX`
4. On success:
   - GCash encrypted
   - tester row created
   - Tester role assigned
   - weekly earnings row created
   - DM welcome embed sent
   - bot log entry posted

### Raw user-facing text examples

- "Please head to #register-here to register."
- "You're already registered. Use /update-gcash to change your GCash number."
- "You're registered! Check your DMs."

## `/update-gcash` Flow

- Active tester only.
- Modal asks for new GCash.
- Same regex validation.
- DB encrypted value updated.
- Confirmation sent in DM and ephemeral response.

## `/tester info`

- No user argument: active tester can view own profile.
- With user argument: admin required.
- Shows profile + all-time aggregate stats.
- Never displays GCash in this command.

## `/tester list`

- Admin only.
- Paginated list (5 per page).
- Includes display name, username, active status, weeks.

## `/tester deactivate` and `/tester reactivate`

- Owner only.
- Deactivate removes tester role and marks inactive.
- Reactivate re-adds tester role and marks active.
- Both actions DM the tester and write bot log entries.

## Embeds/Output

Primary embed builders used:

- `tos_embed()`
- `registration_success_embed(...)`
- `tester_profile_embed(...)`
- `success_embed(...)`
- `warning/error embeds for guard messages`

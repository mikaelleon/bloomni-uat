# Registration and Tester Management

Covers `/register`, application review, `/update-gcash`, `/tester` commands, and owner config that affects registration.

## Commands in This Area

- `/register [invite_code]`
- `/update-gcash`
- `/tester info`, `/tester list`
- `/tester deactivate`, `/tester reactivate`, `/tester unregister`
- Owner: `/config invite-code`, `/config applications-channel`, `/config set` (`bot_description`, `tos_text`)

## `/register` Flow (application gate)

### Guards

- Setup must be complete (`setup_complete` in config).
- Command must be used in the configured **register** channel.
- If already an **active** tester → error: use `/update-gcash` for GCash changes.
- If **deactivated** tester → warning: use `/tester reactivate` or `/tester unregister` to start fresh.
- If a **pending** application exists → error: wait for review.
- If last application was **rejected** → 7-day cooldown before re-applying (ephemeral shows eligible datetime).
- Optional **invite code**: if `invite_code_required` is true, `/register` must include the matching `invite_code_value`.

### User experience

1. **Defer** interaction (avoids Discord interaction timeout during checks).
2. **TOS** embed with accept/decline (TOS text can be customized via `/config set` → `tos_text`).
3. **Commitment** view: user confirms they understand the program is casual / pay is small.
4. **Modal 1 — Identity:** display name, full name (as on GCash), GCash `09XXXXXXXXX`, section/relationship (“how do we know each other”).
5. **“Continue to Step 2”** button (Discord cannot open a second modal from the first modal directly).
6. **Modal 2 — Context:** how they heard about the program (required), availability (optional), device/platform (optional), prior experience (optional), TOS signature (required typed full name). Invite code field is carried from step 1 if used.
7. Application row is stored; an embed is posted to **`channel_applications`** (or bot logs fallback) with **Approve / Reject** buttons for the owner.

### On approve

- GCash encrypted with `FERNET_KEY`; tester row created with all profile fields.
- Tester role assigned.
- **7-page paginated DM guide** (`DMPagedGuideView`, no view timeout): welcome, how it works, rates, limits, payouts, commands, rules — values pulled from live config (`bot_description`, rates, limits).
- Application message updated; buttons removed.

### On reject

- Status set to rejected; optional reason modal.
- Applicant DM with reason and **7-day reapply** notice.
- Application message updated; buttons removed.

### Raw user-facing examples

- “Please head to #register-here to register.”
- “You're already registered. Use /update-gcash…”
- “Your tester account is currently deactivated…” (points to unregister vs reactivate)
- “Invalid or missing invite code.”
- “Application submitted. You will be notified once the owner reviews it.”

## `/update-gcash`

- Active tester only.
- Modal for new number; same `09XXXXXXXXX` validation.
- Encrypted storage updated; confirmation (DM + ephemeral where applicable).

## `/tester info`

- No argument + active tester → own profile and all-time stats (GCash never shown).
- `@user` → admin/owner only; shows that tester if registered.

## `/tester list`

- Admin only; paginated tester summary.

## `/tester deactivate`

- Owner only; interaction is **deferred** early.
- Removes Tester role when member is in guild; marks inactive.
- **Bug cleanup:** for that user’s reports — archive/lock threads, delete bug channel messages when possible, delete DB rows, then **`renumber_bug_ids()`** so remaining bugs stay `BUG-001`, `BUG-002`, …
- Tester DM uses embeds; bot log includes `bugs_removed` count.

## `/tester reactivate`

- Owner only; restores role and active flag; DM embed.

## `/tester unregister`

- Owner only; **fully removes** tester row (and related handling as implemented).
- Same **bug cleanup + renumber** as deactivate so lists stay consistent.
- User can register again later (subject to application flow).

## Embeds and helpers

- `tos_embed(tos_text)`, `confirmation_embed`, `success_embed`, `warning_embed`, `get_welcome_pages(...)` for the DM guide.
- Rate changes (manual `/config set` on rate keys, or `/config economy-auto`) can **broadcast** to announcements and **resend** the paginated guide to active testers (`_broadcast_rate_update`).

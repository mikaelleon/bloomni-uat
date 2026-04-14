# Command Reference by Permission

Quick lookup aligned with the current slash commands in `uat-bot/cogs/`.

## Bot owner only

| Command | Purpose |
|--------|---------|
| `/setup` | First-time setup wizard (roles, channels, rates, features, milestones). |
| `/setup_reset` | Wipe data and allow running `/setup` again (destructive). |
| `/config invite-code` | Toggle invite-code requirement and set the code. |
| `/config applications-channel` | Channel where new registration applications are posted for review. |
| `/config set` | Set `bot_description`, `tos_text`, or any rate/limit key (manual economy). |
| `/config economy-mode` | `manual` or `auto` (auto uses calculated rates from limits/cap). |
| `/config economy-auto` | Compute all four rates plus cap/limits from weekly cap and daily limits. |
| `/config rates` | Open a modal to set all seven rate/limit values at once. |
| `/bugs validate` | Credit bug report rate; status `submitted` → `validated`. |
| `/bugs reject` | Reject a bug (`submitted` or `validated`); optional reason DM. |
| `/bugs resolve` | Resolve a **validated** bug (resolve bonus). |
| `/bugs reopen` | Reopen a resolved bug (reverses resolve bonus). |
| `/suggestion acknowledge` | Credit suggestion submit rate; status `submitted` → `acknowledged`. |
| `/suggestion implement` | Mark implemented (`submitted` or `acknowledged`); pays implement bonus once. |
| `/suggestion dismiss` | Dismiss (`submitted` or `acknowledged`); optional reason. |
| `/tester deactivate` | Remove Tester role; optional bug-thread cleanup and DB bug purge + renumber. |
| `/tester reactivate` | Restore Tester role and active flag. |
| `/tester unregister` | Delete tester record; remove role; purge their bugs and renumber remaining IDs. |

## Admin (UAT Admin role) and owner

| Command | Purpose |
|--------|---------|
| `/tester info` | With `@user`: any tester’s profile. Without: own profile (testers only). |
| `/tester list` | Paginated list of testers. |
| `/earnings` | With `@user`: that user’s week (admins). Without: own week (active tester). |

## Active tester

| Command | Purpose |
|--------|---------|
| `/update-gcash` | Change GCash via modal. |
| `/tester info` | Own profile (no mention). |
| `/bug` / `/bugs submit` | Same bug submission flow. |
| `/bugs list` | Filter includes `open` (= submitted **or** validated, still unresolved). |
| `/bugs info` | Full bug embed + thread link. |
| `/suggest` | Submit a suggestion (no pay until acknowledgement). |
| `/suggestion list` | By status: submitted, acknowledged, implemented, dismissed, all. |
| `/suggestion info` | Full suggestion embed. |
| `/earnings` | This week’s breakdown. |
| `/rates` | Current rates, limits, payout day, economy mode. |
| `/myinfo` | Profile, live daily/weekly reset countdowns (`<t:…:R>`), pending counts. |
| `/mybugs` | Your bugs, optional status filter. |
| `/mysuggestions` | Your suggestions, optional status filter. |
| `/mypending` | Count of bugs awaiting validation and suggestions awaiting acknowledgement. |
| `/streak` | Active-week / senior tester progress. |
| `/history` | Weekly earnings history (`week` = offset). |
| `/leaderboard` | Top testers this week by **total weekly earnings**. |

## Registration / unregistered

| Command | Purpose |
|--------|---------|
| `/register` | Only in configured register channel. TOS → commitment → two modals → application posted for owner approval. Optional `invite_code` if owner enabled it. |

## Notes

- **Economy:** In `auto` mode, `/config set` cannot change numeric rates; use `/config economy-auto` or switch to `manual`.
- **Pay flow:** Bug report and suggestion submit rates pay on **validate** and **acknowledge**, not on raw submission.
- **Embeds:** Bot theme color is `#242429` for standard embeds.
- If setup is incomplete, most commands respond with a short setup/register warning.

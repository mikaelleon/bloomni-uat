# Earnings and Rates

Covers `/earnings` and `/rates`.

## `/earnings`

### Access

- No argument: active tester can view own earnings.
- With user argument: admin required.

### Logic

1. Determine target user.
2. Ensure tester exists.
3. Resolve current week start (Monday in Asia/Manila timezone).
4. Load/create weekly earnings row.
5. Compute per-category earnings using configured rates.
6. Render detailed earnings embed:
   - bugs submitted and earnings
   - bugs resolved and bonus
   - suggestions submitted and earnings
   - suggestions implemented and bonus
   - weekly total
   - cap remaining
   - payout status

## `/rates`

- Shows active config values for:
  - earning rates
  - daily limits
  - weekly cap
  - payout day

## Data Sources

- `earnings` table for counters and totals
- `config` table for rates/limits

## Output Examples

- "Weekly earnings — {display_name}"
- "Cap remaining: ₱X / ₱Y"
- "Payout status: Pending/Paid"

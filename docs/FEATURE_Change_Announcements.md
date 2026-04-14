# Repository change announcements (GitHub → Discord)

When enabled, the bot can **listen for GitHub `push` webhooks** and post a **`#242429`** embed in a configured channel. The embed lists **commit subject lines** (first line of each commit message) and links to the **compare** URL when GitHub sends it.

## Configuration (owner)

| Command | Purpose |
|--------|---------|
| `/config changes channel` | Set the text channel. **Omit** the `channel` option to clear. |
| `/config changes enabled` | Turn announcements on or off. |
| `/config changes status` | Show channel, enabled flag, env hints (port, secret, webhook path). |
| `/config changes test` | Post a **sample** embed to the configured channel (layout check). |

## Environment variables (`uat-bot/.env`)

| Variable | Purpose |
|----------|---------|
| `CHANGELOG_HTTP_ENABLED` | `true` / `1` / `yes` / `on` to start the small HTTP listener inside the bot process. |
| `CHANGELOG_HTTP_PORT` | Port to bind (default `8765`). |
| `GITHUB_WEBHOOK_SECRET` | **Strongly recommended.** GitHub signs payloads with this; the bot returns **401** if the signature does not match. If unset, payloads are accepted (fine for local testing only). |

## Payload URL (local + Cloudflare quick tunnel)

**Formula:** `https://<hostname-from-cloudflared>/webhooks/github`

1. **Terminal A — bot:** `CHANGELOG_HTTP_ENABLED=true`, start `python bot.py`. Console must show `Webhook server listening ... /webhooks/github`.
2. **Terminal B — tunnel (keep running):**  
   `"path\to\cloudflared-windows-amd64.exe" tunnel --url http://127.0.0.1:8765`  
   (use same port as `CHANGELOG_HTTP_PORT`.)
3. Copy **`https://….trycloudflare.com`** from the tunnel output (the box). **Do not** stop this process while GitHub delivers webhooks.
4. **Payload URL** = that URL **+** `/webhooks/github` — e.g. `https://abc.trycloudflare.com/webhooks/github`.

**Helper (Windows):** from `uat-bot` run `.\scripts\payload-url.ps1` — prints port-aware steps and the formula.

**If GitHub shows `530`:** tunnel or bot not running, wrong/stale hostname (restart tunnel → new URL → update webhook), or Payload URL missing `/webhooks/github`. Both processes must be up; then **Redeliver** in Recent Deliveries.

## GitHub setup

1. Ensure `CHANGELOG_HTTP_ENABLED=true` and restart the bot. Check console for: `Webhook server listening on .../webhooks/github`.
2. Expose the port (tunnel or VPS). For Cloudflare, follow **Payload URL** section above.
3. In the GitHub repo: **Settings → Webhooks → Add webhook**
   - **Payload URL:** full URL ending in `/webhooks/github`.
   - **Content type:** `application/json`
   - **Secret:** same value as `GITHUB_WEBHOOK_SECRET` in `.env`
   - **Events:** “Just the push event” (or send everything; non-push events are ignored with `200 ignored`).
4. In Discord: `/config changes channel` → your dev-updates channel, then `/config changes enabled` → **true**.

## Behavior

- Only **`push`** events create an announcement (after `enabled` and channel are set).
- **`ping`** from GitHub (webhook creation test) returns `pong` with HTTP 200.
- If posting fails (permissions, channel gone), a warning is logged to **bot logs** when configured.

## Limitations

- **One listener per bot process** on one port; one webhook URL per deployment.
- Very large pushes are truncated in the embed description (Discord limits).
- Other Git hosts (GitLab, etc.) use different payloads and are not handled by this endpoint.

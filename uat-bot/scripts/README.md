# Helper scripts

## `payload-url.ps1`

Prints the **local** webhook URL and the **exact formula** for the GitHub **Payload URL** when using Cloudflare quick tunnel (`trycloudflare.com`).

```powershell
cd "path\to\uat tracker\uat-bot"
.\scripts\payload-url.ps1
```

Requires: PowerShell 5+ or `pwsh`. Reads `CHANGELOG_HTTP_PORT` from `uat-bot/.env` if present.

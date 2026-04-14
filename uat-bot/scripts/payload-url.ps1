# Prints local webhook URL + exact steps to build GitHub Payload URL (Cloudflare quick tunnel).
# Run from repo:  pwsh -File uat-bot/scripts/payload-url.ps1
# Or: cd uat-bot; .\scripts\payload-url.ps1

$ErrorActionPreference = "Stop"
$uatBotRoot = Split-Path $PSScriptRoot -Parent
$envFile = Join-Path $uatBotRoot ".env"

$port = 8765
$httpEnabled = $false
if (Test-Path $envFile) {
    Get-Content $envFile -ErrorAction SilentlyContinue | ForEach-Object {
        $line = $_.Trim()
        if ($line -match '^\s*CHANGELOG_HTTP_PORT\s*=\s*(\d+)\s*$') {
            $port = [int]$Matches[1]
        }
        if ($line -match '^\s*CHANGELOG_HTTP_ENABLED\s*=\s*(.+)\s*$') {
            $v = $Matches[1].ToLowerInvariant()
            if ($v -in @("1", "true", "yes", "on")) { $httpEnabled = $true }
        }
    }
}

Write-Host ""
Write-Host "=== 1) Bot (terminal A) ===" -ForegroundColor Cyan
Write-Host "  cd uat-bot"
Write-Host "  Set .env: CHANGELOG_HTTP_ENABLED=true , CHANGELOG_HTTP_PORT=$port"
Write-Host "  python bot.py"
Write-Host "  Expect log line: Webhook server listening ... :$port/webhooks/github"
Write-Host ""

Write-Host "=== 2) Local URL (health check: browser may show 405 - OK) ===" -ForegroundColor Cyan
Write-Host "  http://127.0.0.1:$port/webhooks/github"
Write-Host ""

Write-Host "=== 3) Tunnel (terminal B) - keep open while GitHub delivers ===" -ForegroundColor Cyan
Write-Host ('  "C:\path\to\cloudflared-windows-amd64.exe" tunnel --url http://127.0.0.1:' + $port)
Write-Host "  Copy https://....trycloudflare.com from the box."
Write-Host ""

Write-Host "=== 4) GitHub Payload URL (paste in webhook settings) ===" -ForegroundColor Green
Write-Host "  https://<paste-hostname-here>.trycloudflare.com/webhooks/github"
Write-Host "  Content type: application/json"
Write-Host "  Secret: same string as GITHUB_WEBHOOK_SECRET in .env"
Write-Host ""

Write-Host "=== 5) Discord ===" -ForegroundColor Cyan
Write-Host "  /config changes channel  +  /config changes enabled true"
Write-Host ""

if (-not $httpEnabled) {
    Write-Host "NOTE: CHANGELOG_HTTP_ENABLED not true in .env - listener may not start." -ForegroundColor Yellow
}
Write-Host ""

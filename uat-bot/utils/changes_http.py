from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import TYPE_CHECKING

from aiohttp import web

from database import db
from ui import embeds
from utils import config
from utils.logging import log_event

if TYPE_CHECKING:
    import discord
    from discord.ext import commands


def verify_github_signature(body: bytes, signature_header: str | None, secret: str) -> bool:
    if not secret:
        return False
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature_header[7:], expected)


def build_github_push_embed(payload: dict):
    import discord

    repo = payload.get("repository") or {}
    full_name = repo.get("full_name") or "repository"
    compare = payload.get("compare") or ""
    ref = payload.get("ref") or ""
    branch = ref.replace("refs/heads/", "", 1) if ref.startswith("refs/heads/") else (ref or "?")
    pusher = (payload.get("pusher") or {}).get("name") or "?"

    commits = payload.get("commits") or []
    head = payload.get("head_commit") or {}

    lines: list[str] = []
    for c in commits[-25:]:
        raw_msg = (c.get("message") or "").strip()
        first_line = raw_msg.split("\n", 1)[0].strip()[:240]
        short_sha = (c.get("id") or "")[:7]
        lines.append(f"`{short_sha}` {first_line}")

    if not lines and head:
        raw = (head.get("message") or "").strip()
        first_line = raw.split("\n", 1)[0].strip()
        short_sha = (head.get("id") or "")[:7]
        lines.append(f"`{short_sha}` {first_line[:400]}")

    body = "\n".join(lines) if lines else "*(no commit messages in payload)*"
    if len(body) > 3900:
        body = body[:3897] + "…"

    e = discord.Embed(
        title=f"Repository updated — {full_name}",
        description=body,
        color=embeds.EMBED_COLOR,
        url=compare if compare else None,
    )
    e.set_footer(text="GitHub push")
    e.add_field(name="Branch", value=f"`{branch}`", inline=True)
    e.add_field(name="Pusher", value=pusher[:256], inline=True)
    e.add_field(name="Commits in push", value=str(len(commits)), inline=True)
    if compare:
        e.add_field(name="Compare", value=f"[Open diff]({compare})", inline=False)
    return e


async def post_github_push_embed(bot: "commands.Bot", payload: dict) -> None:
    enabled = (await db.get_config("changes_announce_enabled")).strip().lower() == "true"
    if not enabled:
        return
    ch = await config.get_channel(bot, "channel_changes_announcements")
    if ch is None:
        await log_event(
            bot,
            "CHANGES_ANNOUNCE_SKIP",
            {"reason": "no_channel_configured"},
            level="WARNING",
        )
        return

    embed = build_github_push_embed(payload)
    try:
        await ch.send(embed=embed)
    except Exception as exc:  # noqa: BLE001
        await log_event(
            bot,
            "CHANGES_ANNOUNCE_FAIL",
            {"error": repr(exc), "channel_id": str(ch.id)},
            level="WARNING",
        )
        return

    repo = (payload.get("repository") or {}).get("full_name", "")
    await log_event(
        bot,
        "CHANGES_ANNOUNCE",
        {"repository": repo, "channel_id": str(ch.id)},
    )


async def github_webhook_handler(request: web.Request) -> web.Response:
    bot = request.app["bot"]
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "").strip()

    body = await request.read()
    sig = request.headers.get("X-Hub-Signature-256")

    if secret:
        if not verify_github_signature(body, sig, secret):
            return web.Response(status=401, text="invalid signature")
    event = (request.headers.get("X-GitHub-Event") or "").strip()

    if event == "ping":
        return web.Response(text="pong")

    if event != "push":
        return web.Response(text="ignored")

    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return web.Response(status=400, text="bad json")

    await post_github_push_embed(bot, data)
    return web.Response(text="ok")


def create_changes_app(bot: "commands.Bot") -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app.router.add_post("/webhooks/github", github_webhook_handler)
    return app


async def start_changes_server(bot: "commands.Bot") -> tuple[web.AppRunner, web.TCPSite] | None:
    if os.getenv("CHANGELOG_HTTP_ENABLED", "").strip().lower() not in ("1", "true", "yes", "on"):
        return None
    raw_port = os.getenv("CHANGELOG_HTTP_PORT", "8765").strip()
    try:
        port = int(raw_port)
    except ValueError:
        port = 8765
    app = create_changes_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(
        f"[changes] Webhook server listening on http://0.0.0.0:{port}/webhooks/github "
        "(set GITHUB_WEBHOOK_SECRET in .env for production)"
    )
    return runner, site


async def stop_changes_server(
    pair: tuple[web.AppRunner, web.TCPSite] | None,
) -> None:
    if not pair:
        return
    runner, _site = pair
    await runner.cleanup()

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

import aiosqlite

DB_PATH = Path(__file__).resolve().parent.parent / "uat_bot.db"

_conn: aiosqlite.Connection | None = None

DEFAULT_CONFIG = {
    "bug_report_rate": "15",
    "bug_resolve_bonus": "10",
    "suggestion_submit_rate": "10",
    "suggestion_implement_bonus": "15",
    "weekly_cap": "250",
    "daily_bug_limit": "3",
    "daily_suggestion_limit": "2",
    "reminder_time": "20:00",
    "payout_day": "Monday",
    "feature_list": "Commission System\nBug Tracker\nPayout System\nRegistration\nOther",
    "channel_bug_reports": "",
    "channel_suggestions": "",
    "channel_payout_log": "",
    "channel_bot_logs": "",
    "channel_announcements": "",
    "channel_register_here": "",
    "channel_guidelines": "",
    "role_tester": "",
    "role_admin": "",
    "role_senior_tester": "",
    "setup_complete": "false",
}


async def init_db() -> None:
    global _conn
    if _conn is not None:
        await _conn.close()
    _conn = await aiosqlite.connect(DB_PATH)
    _conn.row_factory = aiosqlite.Row
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    with open(schema_path, encoding="utf-8") as f:
        await _conn.executescript(f.read())
    await _conn.commit()
    cur = await _conn.execute("SELECT COUNT(*) FROM config")
    row = await cur.fetchone()
    if row and row[0] == 0:
        for k, v in DEFAULT_CONFIG.items():
            await _conn.execute("INSERT INTO config (key, value) VALUES (?, ?)", (k, v))
        await _conn.commit()


async def reset_db() -> None:
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None
    if DB_PATH.exists():
        os.remove(DB_PATH)
    await init_db()


def _db() -> aiosqlite.Connection:
    if _conn is None:
        raise RuntimeError("Database not initialized")
    return _conn


# --- Config ---


async def get_config(key: str) -> str:
    cur = await _db().execute("SELECT value FROM config WHERE key = ?", (key,))
    row = await cur.fetchone()
    if row is None:
        return ""
    return str(row["value"])


async def set_config(key: str, value: str) -> None:
    await _db().execute(
        "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    await _db().commit()


async def get_all_config() -> dict:
    cur = await _db().execute("SELECT key, value FROM config")
    rows = await cur.fetchall()
    return {r["key"]: r["value"] for r in rows}


# --- Testers ---


async def get_tester(user_id: str) -> dict | None:
    cur = await _db().execute("SELECT * FROM testers WHERE user_id = ?", (user_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def create_tester(
    user_id: str,
    display_name: str,
    gcash_encrypted: str,
    registered_at: datetime,
) -> None:
    await _db().execute(
        """INSERT INTO testers (user_id, display_name, gcash_number, registered_at)
           VALUES (?, ?, ?, ?)""",
        (user_id, display_name, gcash_encrypted, registered_at.isoformat()),
    )
    await _db().commit()


async def update_tester_gcash(user_id: str, gcash_encrypted: str) -> None:
    await _db().execute(
        "UPDATE testers SET gcash_number = ? WHERE user_id = ?",
        (gcash_encrypted, user_id),
    )
    await _db().commit()


async def deactivate_tester(user_id: str) -> None:
    await _db().execute("UPDATE testers SET is_active = 0 WHERE user_id = ?", (user_id,))
    await _db().commit()


async def reactivate_tester(user_id: str) -> None:
    await _db().execute("UPDATE testers SET is_active = 1 WHERE user_id = ?", (user_id,))
    await _db().commit()


async def get_all_testers(active_only: bool = True) -> list[dict]:
    if active_only:
        cur = await _db().execute("SELECT * FROM testers WHERE is_active = 1 ORDER BY display_name")
    else:
        cur = await _db().execute("SELECT * FROM testers ORDER BY display_name")
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


# --- Bugs ---


async def get_next_bug_id() -> str:
    cur = await _db().execute(
        """SELECT bug_id FROM bugs
           ORDER BY CAST(SUBSTR(bug_id, 5) AS INTEGER) DESC LIMIT 1"""
    )
    row = await cur.fetchone()
    if row is None:
        return "BUG-001"
    n = int(row["bug_id"].split("-")[1]) + 1
    return f"BUG-{n:03d}"


async def create_bug(
    bug_id: str,
    reporter_id: str,
    title: str,
    steps: str,
    actual: str,
    expected: str,
    severity: str,
    submitted_at: datetime,
) -> None:
    await _db().execute(
        """INSERT INTO bugs (
            bug_id, reporter_id, title, steps, actual, expected, severity,
            status, submitted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)""",
        (
            bug_id,
            reporter_id,
            title,
            steps,
            actual,
            expected,
            severity,
            submitted_at.isoformat(),
        ),
    )
    await _db().commit()


async def get_bug(bug_id: str) -> dict | None:
    cur = await _db().execute("SELECT * FROM bugs WHERE bug_id = ?", (bug_id.upper(),))
    row = await cur.fetchone()
    if row is None:
        cur = await _db().execute("SELECT * FROM bugs WHERE bug_id = ?", (bug_id,))
        row = await cur.fetchone()
    return dict(row) if row else None


async def update_bug_status(bug_id: str, status: str, resolved_at: datetime | None = None) -> None:
    if resolved_at is None:
        await _db().execute(
            "UPDATE bugs SET status = ?, resolved_at = NULL WHERE bug_id = ?",
            (status, bug_id),
        )
    else:
        await _db().execute(
            "UPDATE bugs SET status = ?, resolved_at = ? WHERE bug_id = ?",
            (status, resolved_at.isoformat(), bug_id),
        )
    await _db().commit()


async def update_bug_thread(bug_id: str, thread_id: str) -> None:
    await _db().execute("UPDATE bugs SET thread_id = ? WHERE bug_id = ?", (thread_id, bug_id))
    await _db().commit()


async def update_bug_message_id(bug_id: str, message_id: str) -> None:
    await _db().execute("UPDATE bugs SET message_id = ? WHERE bug_id = ?", (message_id, bug_id))
    await _db().commit()


async def get_bugs_by_status(status: str) -> list[dict]:
    if status == "all":
        cur = await _db().execute("SELECT * FROM bugs ORDER BY submitted_at DESC")
    else:
        cur = await _db().execute(
            "SELECT * FROM bugs WHERE status = ? ORDER BY submitted_at DESC", (status,)
        )
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_all_open_bug_titles() -> list[str]:
    cur = await _db().execute(
        "SELECT title FROM bugs WHERE status = 'open'"
    )
    rows = await cur.fetchall()
    return [r["title"] for r in rows]


# --- Suggestions ---


async def get_next_suggestion_id() -> str:
    cur = await _db().execute(
        """SELECT suggestion_id FROM suggestions
           ORDER BY CAST(SUBSTR(suggestion_id, 5) AS INTEGER) DESC LIMIT 1"""
    )
    row = await cur.fetchone()
    if row is None:
        return "SUG-001"
    n = int(row["suggestion_id"].split("-")[1]) + 1
    return f"SUG-{n:03d}"


async def create_suggestion(
    suggestion_id: str,
    submitter_id: str,
    feature_tag: str,
    title: str,
    description: str,
    submitted_at: datetime,
) -> None:
    await _db().execute(
        """INSERT INTO suggestions (
            suggestion_id, submitter_id, feature_tag, title, description,
            status, submitted_at
        ) VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
        (
            suggestion_id,
            submitter_id,
            feature_tag,
            title,
            description,
            submitted_at.isoformat(),
        ),
    )
    await _db().commit()


async def get_suggestion(suggestion_id: str) -> dict | None:
    cur = await _db().execute(
        "SELECT * FROM suggestions WHERE suggestion_id = ?", (suggestion_id.upper(),)
    )
    row = await cur.fetchone()
    if row is None:
        cur = await _db().execute(
            "SELECT * FROM suggestions WHERE suggestion_id = ?", (suggestion_id,)
        )
        row = await cur.fetchone()
    return dict(row) if row else None


async def update_suggestion_status(
    suggestion_id: str,
    status: str,
    dismiss_reason: str | None = None,
    actioned_at: datetime | None = None,
) -> None:
    await _db().execute(
        """UPDATE suggestions SET status = ?, dismiss_reason = ?, actioned_at = ?
           WHERE suggestion_id = ?""",
        (
            status,
            dismiss_reason,
            actioned_at.isoformat() if actioned_at else None,
            suggestion_id,
        ),
    )
    await _db().commit()


async def update_suggestion_message_id(suggestion_id: str, message_id: str) -> None:
    await _db().execute(
        "UPDATE suggestions SET message_id = ? WHERE suggestion_id = ?",
        (message_id, suggestion_id),
    )
    await _db().commit()


async def get_suggestions_by_status(status: str) -> list[dict]:
    if status == "all":
        cur = await _db().execute("SELECT * FROM suggestions ORDER BY submitted_at DESC")
    else:
        cur = await _db().execute(
            "SELECT * FROM suggestions WHERE status = ? ORDER BY submitted_at DESC",
            (status,),
        )
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


# --- Earnings ---


async def get_or_create_earnings(user_id: str, week_start: date) -> dict:
    ws = week_start.isoformat()
    cur = await _db().execute(
        "SELECT * FROM earnings WHERE user_id = ? AND week_start = ?",
        (user_id, ws),
    )
    row = await cur.fetchone()
    if row:
        return dict(row)
    await _db().execute(
        """INSERT INTO earnings (user_id, week_start) VALUES (?, ?)""",
        (user_id, ws),
    )
    await _db().commit()
    cur = await _db().execute(
        "SELECT * FROM earnings WHERE user_id = ? AND week_start = ?",
        (user_id, ws),
    )
    row = await cur.fetchone()
    return dict(row) if row else {}


_ALLOWED_EARNINGS_FIELDS = frozenset(
    {
        "bugs_submitted",
        "bugs_resolved",
        "suggestions_submitted",
        "suggestions_implemented",
        "loyalty_bonus",
        "total_earned",
    }
)


async def add_earnings(user_id: str, week_start: date, field: str, amount: int) -> None:
    if field not in _ALLOWED_EARNINGS_FIELDS:
        raise ValueError(f"Invalid earnings field: {field}")
    await get_or_create_earnings(user_id, week_start)
    ws = week_start.isoformat()
    await _db().execute(
        f"UPDATE earnings SET {field} = {field} + ? WHERE user_id = ? AND week_start = ?",
        (amount, user_id, ws),
    )
    await _db().commit()


async def get_weekly_total(user_id: str, week_start: date) -> int:
    row = await get_or_create_earnings(user_id, week_start)
    return int(row.get("total_earned") or 0)


# --- Daily counts ---


async def get_daily_counts(user_id: str, today: date) -> dict:
    cur = await _db().execute(
        "SELECT * FROM daily_counts WHERE user_id = ? AND date = ?",
        (user_id, today.isoformat()),
    )
    row = await cur.fetchone()
    if row:
        return dict(row)
    return {
        "user_id": user_id,
        "date": today.isoformat(),
        "bugs_today": 0,
        "suggestions_today": 0,
    }


_DAILY_FIELDS = frozenset({"bugs_today", "suggestions_today"})


async def increment_daily_count(user_id: str, today: date, field: str) -> None:
    if field not in _DAILY_FIELDS:
        raise ValueError(f"Invalid daily field: {field}")
    d = today.isoformat()
    if field == "bugs_today":
        await _db().execute(
            """INSERT INTO daily_counts (user_id, date, bugs_today, suggestions_today)
               VALUES (?, ?, 1, 0)
               ON CONFLICT(user_id, date) DO UPDATE SET bugs_today = bugs_today + 1""",
            (user_id, d),
        )
    else:
        await _db().execute(
            """INSERT INTO daily_counts (user_id, date, bugs_today, suggestions_today)
               VALUES (?, ?, 0, 1)
               ON CONFLICT(user_id, date) DO UPDATE SET suggestions_today = suggestions_today + 1""",
            (user_id, d),
        )
    await _db().commit()


# --- Stats (for /tester info) ---


async def get_tester_all_time_stats(user_id: str) -> dict:
    cur = await _db().execute(
        "SELECT COUNT(*) AS c FROM bugs WHERE reporter_id = ?", (user_id,)
    )
    bugs_sub = (await cur.fetchone())["c"]
    cur = await _db().execute(
        "SELECT COUNT(*) AS c FROM bugs WHERE reporter_id = ? AND status = 'resolved'",
        (user_id,),
    )
    bugs_res = (await cur.fetchone())["c"]
    cur = await _db().execute(
        "SELECT COUNT(*) AS c FROM suggestions WHERE submitter_id = ?", (user_id,)
    )
    sug_sub = (await cur.fetchone())["c"]
    cur = await _db().execute(
        "SELECT COUNT(*) AS c FROM suggestions WHERE submitter_id = ? AND status = 'implemented'",
        (user_id,),
    )
    sug_imp = (await cur.fetchone())["c"]
    cur = await _db().execute(
        "SELECT COALESCE(SUM(total_earned), 0) AS s FROM earnings WHERE user_id = ?",
        (user_id,),
    )
    total_earned = int((await cur.fetchone())["s"])
    return {
        "bugs_submitted": bugs_sub,
        "bugs_resolved": bugs_res,
        "suggestions_submitted": sug_sub,
        "suggestions_implemented": sug_imp,
        "total_earned_all_time": total_earned,
    }


# --- Milestones ---


async def create_milestone(name: str, description: str, rate_changes: str) -> None:
    await _db().execute(
        "INSERT INTO milestones (name, description, rate_changes) VALUES (?, ?, ?)",
        (name, description, rate_changes),
    )
    await _db().commit()

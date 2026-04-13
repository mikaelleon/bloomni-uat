import re


def parse_snowflake(text: str) -> int | None:
    if not text:
        return None
    m = re.search(r"(\d{15,25})", text.strip())
    return int(m.group(1)) if m else None


def parse_rates_block(text: str) -> dict[str, int] | None:
    keys = {
        "bug_report_rate",
        "bug_resolve_bonus",
        "suggestion_submit_rate",
        "suggestion_implement_bonus",
        "weekly_cap",
        "daily_bug_limit",
        "daily_suggestion_limit",
    }
    out: dict[str, int] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if k not in keys:
            continue
        try:
            n = int(v)
            if n < 0:
                return None
            out[k] = n
        except ValueError:
            return None
    if set(out.keys()) != keys:
        return None
    return out

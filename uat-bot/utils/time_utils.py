from datetime import date, datetime, timedelta

import pytz

PHT = pytz.timezone("Asia/Manila")


def now_pht() -> datetime:
    return datetime.now(PHT)


def today_pht() -> date:
    return now_pht().date()


def get_week_start(d: date | None = None) -> date:
    if d is None:
        d = today_pht()
    # Monday as week start
    return d - timedelta(days=d.weekday())

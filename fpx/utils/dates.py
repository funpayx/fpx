import re
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Moscow")

_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
_RX = re.compile(r"(\d{1,2})\s+([а-я]+)(?:\s+(\d{4}))?,?\s*(?:в\s+)?(\d{1,2}):(\d{2})(?::(\d{2}))?")


def parse_funpay_datetime(text: str, now: datetime | None = None) -> datetime | None:
    m = _RX.search(text)
    if not m or m.group(2) not in _MONTHS:
        return None
    now = now or datetime.now(TZ)
    day, mon, year, h, mi, sec = m.groups()
    dt = datetime(int(year) if year else now.year, _MONTHS[mon], int(day),
                  int(h), int(mi), int(sec or 0), tzinfo=TZ)
    if not year and dt > now:
        dt = dt.replace(year=dt.year - 1)
    return dt

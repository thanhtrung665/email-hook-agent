"""Lich hoat dong (khung gio) cho ingestion agent."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings

logger = logging.getLogger(__name__)


def _parse_hhmm(text: str) -> tuple[int, int]:
    parts = text.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"expected HH:MM, got {text!r}")
    hour = int(parts[0])
    minute = int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"invalid HH:MM {text!r}")
    return hour, minute


def _normalize_days(raw: str) -> set[int]:
    name_to_idx = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    result: set[int] = set()
    for token in raw.lower().split(","):
        token = token.strip()
        if not token:
            continue
        if token.isdigit():
            result.add(int(token) % 7)
        elif token in name_to_idx:
            result.add(name_to_idx[token])
        else:
            raise ValueError(f"unknown weekday {token!r}")
    return result or set(range(7))


def is_active(dt: datetime | None = None) -> bool:
    zone = ZoneInfo(settings.AGENT_TIMEZONE)
    now = dt.astimezone(zone) if dt else datetime.now(ZoneInfo(settings.AGENT_TIMEZONE))

    allowed_days = _normalize_days(settings.AGENT_ACTIVE_DAYS)
    if now.weekday() not in allowed_days:
        return False

    start_h, start_m = _parse_hhmm(settings.AGENT_ACTIVE_START)
    end_h, end_m = _parse_hhmm(settings.AGENT_ACTIVE_END)
    start = start_h * 60 + start_m
    end = end_h * 60 + end_m
    cur = now.hour * 60 + now.minute

    if start == end:
        return True
    if start < end:
        return start <= cur < end
    # qua dem
    return cur >= start or cur < end


def next_wake_after_pause(now: datetime | None = None) -> datetime:
    """
    Tra lai thoi diem (timezone-aware) ke tiep ma is_active() = True.
    Quet tung ngay trong 8 ngay toi va tim HH:MM gan nhat >= now.
    Neu khung la qua dem, moment kich hoat ke tiep se la hom nay 1 lan
    duy nhat trong ngay.
    """
    zone = ZoneInfo(settings.AGENT_TIMEZONE)
    base = (now.astimezone(zone) if now else datetime.now(zone)).replace(second=0, microsecond=0)
    allowed_days = _normalize_days(settings.AGENT_ACTIVE_DAYS)
    start_h, start_m = _parse_hhmm(settings.AGENT_ACTIVE_START)

    for offset in range(9):
        candidate_day = (base + timedelta(days=offset)).date()
        weekday = candidate_day.weekday()
        if weekday not in allowed_days:
            continue

        # voi khung qua dem, moi ngay deu co 1 khoang kich hoat tu START
        # cho den het dem / sang hom sau — moment bat dau kich hoat
        # la midnight cua ngay do + START time
        wake = datetime(candidate_day.year, candidate_day.month, candidate_day.day, start_h, start_m, tzinfo=zone)
        if wake <= base:
            continue

        # neu khung qua dem va wake thuoc hom nay chay truoc base nhưng van
        # trong khung: thi is_active(base) da True — ham nay chi duoc goi
        # khi is_active()==False, nen co the skip.
        return wake

    # fallback: 1 phut nua
    return base + timedelta(minutes=1)


def describe_schedule() -> str:
    name_to_day = {0: "Thu2", 1: "Thu3", 2: "Thu4", 3: "Thu5", 4: "Thu6", 5: "Thu7", 6: "CN"}
    days = _normalize_days(settings.AGENT_ACTIVE_DAYS)
    day_label = ",".join(name_to_day[i] for i in sorted(days))
    return f"{settings.AGENT_ACTIVE_START} -> {settings.AGENT_ACTIVE_END} {day_label} ({settings.AGENT_TIMEZONE})"

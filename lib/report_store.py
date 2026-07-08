"""
In-app log store for the daily briefings. Instead of loose .md files, reports are
saved here (data/reports.json) as dated morning/evening entries, and the app reads
them straight from this store. Keeps ~a week (14 entries = 7 days x 2 slots).
"""
import os
import json
from datetime import datetime

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_PATH = os.path.join(_DIR, "reports.json")
_KEEP = 14  # 7 days of morning + evening


def _read() -> list[dict]:
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _write(entries: list[dict]):
    os.makedirs(_DIR, exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def save(slot: str, content: str, when: datetime | None = None):
    """Save/overwrite the entry for a given date+slot ('morning'/'evening')."""
    when = when or datetime.now()
    date = when.strftime("%Y-%m-%d")
    slot = slot.lower()
    entries = [e for e in _read() if not (e["date"] == date and e["slot"] == slot)]
    entries.append({
        "date": date,
        "slot": slot,
        "time": when.strftime("%H:%M"),
        "content": content,
    })
    # newest first, keep the most recent _KEEP
    entries.sort(key=lambda e: (e["date"], 0 if e["slot"] == "morning" else 1), reverse=True)
    _write(entries[:_KEEP])


def load_all() -> list[dict]:
    """All stored entries, newest first."""
    entries = _read()
    entries.sort(key=lambda e: (e["date"], 0 if e["slot"] == "morning" else 1), reverse=True)
    return entries


def latest(slot: str) -> dict | None:
    for e in load_all():
        if e["slot"] == slot.lower():
            return e
    return None

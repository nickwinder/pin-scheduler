# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Compute the next free posting slots from config.yaml and manifest.csv.

CLI:
    uv run --no-project scripts/slots.py --count 5
Prints one local ISO datetime per line.
"""
import argparse
from datetime import datetime, time, timedelta

import yaml

from manifest import read_rows


def next_slots(*, window_start, window_end, interval, taken, now, count,
               margin=timedelta(minutes=20)):
    if window_start >= window_end:
        raise ValueError("window_start must be before window_end")
    if interval <= timedelta(0):
        raise ValueError("interval must be positive")
    earliest = now + margin
    slots = []
    day = now.date()
    while len(slots) < count:
        candidate = datetime.combine(day, window_start)
        day_end = datetime.combine(day, window_end)
        while candidate <= day_end and len(slots) < count:
            if candidate >= earliest and candidate not in taken:
                slots.append(candidate)
            candidate += interval
        day += timedelta(days=1)
    return slots


def taken_from_rows(rows):
    taken = set()
    for r in rows:
        if r["status"] == "scheduled" and r["scheduled_time"]:
            dt = datetime.fromisoformat(r["scheduled_time"])
            if dt.tzinfo is not None:
                raise ValueError(f"scheduled_time must be naive local time: {r['scheduled_time']}")
            taken.add(dt)
    return taken


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--manifest", default="manifest.csv")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    taken = taken_from_rows(read_rows(args.manifest))
    slots = next_slots(
        window_start=time.fromisoformat(cfg["window"]["start"]),
        window_end=time.fromisoformat(cfg["window"]["end"]),
        interval=timedelta(minutes=cfg["interval_minutes"]),
        taken=taken,
        now=datetime.now(),
        count=args.count,
        margin=timedelta(minutes=cfg.get("margin_minutes", 20)),
    )
    for slot in slots:
        print(slot.isoformat(timespec="minutes"))


if __name__ == "__main__":
    main()

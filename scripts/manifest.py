"""Read and update manifest.csv — the single source of truth for pin state.

CLI:
    uv run --no-project scripts/manifest.py add <filename> <title> <description>
    uv run --no-project scripts/manifest.py mark <filename> <status> [--time ISO] [--error MSG]
    uv run --no-project scripts/manifest.py capacity [--cap N]
"""
import argparse
import csv
from datetime import datetime
from pathlib import Path

FIELDS = ["filename", "title", "description", "status", "scheduled_time", "error"]
STATUSES = ["draft", "approved", "scheduled", "failed"]
QUEUE_CAP = 10


def read_rows(path):
    path = Path(path)
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path, rows):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def append_row(path, filename, title, description):
    rows = read_rows(path)
    rows.append({
        "filename": filename, "title": title, "description": description,
        "status": "draft", "scheduled_time": "", "error": "",
    })
    write_rows(path, rows)


def mark(path, filename, status, scheduled_time="", error=""):
    if status == "scheduled" and not scheduled_time:
        raise ValueError("scheduled requires scheduled_time")
    rows = read_rows(path)
    for row in rows:
        if row["filename"] == filename:
            row["status"] = status
            row["scheduled_time"] = scheduled_time
            row["error"] = error
            write_rows(path, rows)
            return
    raise KeyError(f"{filename} not in manifest")


def remaining_capacity(rows, now, cap=QUEUE_CAP):
    queued = [
        r for r in rows
        if r["status"] == "scheduled"
        and r["scheduled_time"]
        and datetime.fromisoformat(r["scheduled_time"]) > now
    ]
    return cap - len(queued)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="manifest.csv")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_add = sub.add_parser("add")
    p_add.add_argument("filename")
    p_add.add_argument("title")
    p_add.add_argument("description")
    p_mark = sub.add_parser("mark")
    p_mark.add_argument("filename")
    p_mark.add_argument("status", choices=STATUSES)
    p_mark.add_argument("--time", default="")
    p_mark.add_argument("--error", default="")
    p_cap = sub.add_parser("capacity")
    p_cap.add_argument("--cap", type=int, default=QUEUE_CAP)
    args = parser.parse_args()

    if args.cmd == "add":
        append_row(args.manifest, args.filename, args.title, args.description)
    elif args.cmd == "mark":
        mark(args.manifest, args.filename, args.status, args.time, args.error)
    elif args.cmd == "capacity":
        print(remaining_capacity(read_rows(args.manifest), now=datetime.now(), cap=args.cap))


if __name__ == "__main__":
    main()

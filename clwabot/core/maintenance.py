#!/usr/bin/env python3
from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RUN_DIR = BASE_DIR.parent / ".run"
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = BASE_DIR / "data" / "backups"


def rotate_logs(days: int = 7) -> int:
    if not RUN_DIR.exists():
        return 0
    cutoff = datetime.now() - timedelta(days=days)
    removed = 0
    for path in RUN_DIR.glob("*.log"):
        dt = datetime.fromtimestamp(path.stat().st_mtime)
        if dt < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def backup_json_files() -> int:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    copied = 0
    for path in DATA_DIR.glob("*.json"):
        target = BACKUP_DIR / f"{path.stem}_{ts}.json"
        shutil.copy2(path, target)
        copied += 1
    return copied


def main() -> int:
    copied = backup_json_files()
    removed = rotate_logs()
    print(f"backup_json_files={copied}")
    print(f"rotate_logs_removed={removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

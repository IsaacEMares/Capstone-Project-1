from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import utcnow_iso


class TradeLog:
    """Real-time append-only trade journal (Phase 4.1 foundations).

    Every action — entry, exit, stop/target modification, control change,
    skipped setup, rejected order — is written the moment it happens, with
    its reasoning. Records are JSONL; open the file mid-session to watch live.
    """

    def __init__(self, data_dir: Path):
        self.path = data_dir / "trade_log.jsonl"
        data_dir.mkdir(parents=True, exist_ok=True)

    def append(self, kind: str, **payload: Any) -> dict:
        record = {"ts": utcnow_iso(), "kind": kind, **payload}
        with self.path.open("a") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def recent(self, limit: int = 50) -> list[dict]:
        if not self.path.exists():
            return []
        records = []
        for line in self.path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return list(reversed(records[-limit:]))

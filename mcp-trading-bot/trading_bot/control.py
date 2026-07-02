from __future__ import annotations

import json
from pathlib import Path

from .models import BotState, utcnow_iso


class Control:
    """ACTIVE / PAUSED / STOPPED toggle (Phase 1.5). Defaults to PAUSED — the
    bot never trades until Isaac explicitly activates it."""

    def __init__(self, data_dir: Path):
        self.path = data_dir / "control.json"
        data_dir.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(BotState.PAUSED, "initial state — activate explicitly to allow trading")

    def _write(self, state: BotState, reason: str) -> dict:
        record = {"state": state.value, "reason": reason, "updated_at": utcnow_iso()}
        self.path.write_text(json.dumps(record, indent=2))
        return record

    def get(self) -> dict:
        return json.loads(self.path.read_text())

    @property
    def state(self) -> BotState:
        return BotState(self.get()["state"])

    def set(self, state: BotState, reason: str) -> dict:
        return self._write(state, reason)

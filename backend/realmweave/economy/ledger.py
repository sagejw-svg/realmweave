"""The world ledger: one audited record of every coin that moves.

Slice A of the deep-economy work rests on a single idea: money never appears or
vanishes silently. Every transfer (a trade, a wage, rent, a fine, restitution, a
relief grant, a world subsidy) is written here as one append-only entry, so the
economy can be inspected, balanced, and debugged after the fact.

Entries are kept in memory (capped, for snapshots and dashboards) and, when a
file is attached, mirrored to a JSONL file - one compact JSON object per line -
which the hosted world writes beside its save. The ledger is a log, not core
state: losing it never corrupts a world, so persistence only keeps a recent tail
for continuity.
"""
from __future__ import annotations
import atexit
import json
import os
from typing import List, Optional

# Well-known non-agent parties. Agent ids never collide with these.
TREASURY = "treasury"   # the village coffer: rent and fines in, wages and relief out
WORLD = "world"         # the world itself: an unbacked source/sink (subsidies, NPC supply)

LEDGER_CAP = 5000       # entries kept in memory (and persisted tail is smaller)
PERSIST_TAIL = 500      # how many recent entries survive a save/load


class Ledger:
    """An append-only economic log. Cheap to write, easy to read back."""

    def __init__(self, cap: int = LEDGER_CAP):
        self.cap = cap
        self.entries: List[dict] = []
        self.total = 0                       # lifetime count (survives the cap)
        self._path: Optional[str] = None
        self._fh = None

    # ---- writing -------------------------------------------------------
    def record(self, minutes: int, day: int, kind: str, src: str, dst: str,
               amount: int, note: str = "") -> dict:
        """Append one movement. `src`/`dst` are agent ids or well-known parties
        (TREASURY, WORLD, or a `player:<name>` label)."""
        entry = {"t": int(minutes), "day": int(day), "kind": kind,
                 "src": src, "dst": dst, "amount": int(amount), "note": note}
        self.entries.append(entry)
        self.total += 1
        if len(self.entries) > self.cap:
            # drop the oldest in-memory rows; the JSONL file keeps the full history
            del self.entries[: len(self.entries) - self.cap]
        if self._fh is not None:
            try:
                self._fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
                self._fh.flush()
            except Exception:
                pass
        return entry

    # ---- optional file mirror -----------------------------------------
    def attach(self, path: str) -> None:
        """Mirror every future entry to a JSONL file (opened for append)."""
        abspath = os.path.abspath(path)
        os.makedirs(os.path.dirname(abspath), exist_ok=True)
        self._path = abspath
        self._fh = open(abspath, "a", encoding="utf-8")
        atexit.register(self.close)     # ensure a clean close at interpreter exit

    def close(self) -> None:
        if self._fh is not None:
            try:
                self._fh.close()
            finally:
                self._fh = None

    # ---- reading -------------------------------------------------------
    def tail(self, n: int = 20) -> List[dict]:
        return self.entries[-n:]

    # ---- persistence ---------------------------------------------------
    def to_dict(self) -> dict:
        return {"total": self.total, "entries": self.entries[-PERSIST_TAIL:]}

    def load(self, data: dict) -> None:
        self.entries = list(data.get("entries", []))
        self.total = int(data.get("total", len(self.entries)))

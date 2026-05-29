"""CSV debug logger for finetuning the strike detector. DESKTOP-ONLY / debug-only.

Writes one row per logged finger per frame from the detector's internal state (via
the detector's debug_sink hook), plus a `#`-commented metadata header (measured FPS,
frame windows, per-finger contact zeros, arm clearance). Off by default; enabled via
config.DEBUG_LOG_ENABLED. Analyse afterwards to tune the thresholds. Not portable —
lives in output/ alongside the other desktop consumers.
"""
from __future__ import annotations

import csv
from typing import Iterable, Optional, Sequence

# Fixed column order so the CSV is stable across runs.
COLUMNS = [
    "ts_ms", "finger", "hand", "raw_y", "smoothed_y", "velocity_pxps", "depth",
    "armed", "was_fast", "deepest_y", "contact_zero_y", "arm_line_y",
    "event", "fired", "strike_speed",
]


def _fmt(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return value


class DebugLogger:
    """Buffered CSV writer. Call `write_meta(...)` once (before any record), then
    `record(dict)` per frame, then `close()`."""

    def __init__(self, path: str, hands: Optional[Iterable[str]] = None) -> None:
        self._path = path
        self._file = open(path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=COLUMNS, extrasaction="ignore")
        self._hands = set(hands) if hands else None  # filter by handedness value; None = all
        self._header_written = False
        self._rows = 0

    def write_meta(self, lines: Sequence[str]) -> None:
        """Write `#`-prefixed comment lines (skipped by pandas with comment='#')."""
        for line in lines:
            self._file.write(f"# {line}\n")

    def record(self, rec: dict) -> None:
        if self._hands is not None and rec.get("hand") not in self._hands:
            return
        if not self._header_written:
            self._writer.writeheader()
            self._header_written = True
        self._writer.writerow({k: _fmt(rec.get(k)) for k in COLUMNS})
        self._rows += 1

    def close(self) -> None:
        try:
            self._file.close()
        except Exception:
            pass
        print(f"[debug-log] wrote {self._rows} rows to {self._path}")

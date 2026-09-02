from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RuntimeMetrics:
    """Operational telemetry for the trading runtime."""

    started_at: datetime | None
    last_scan_at: datetime | None
    last_successful_scan_at: datetime | None
    last_reconciliation_at: datetime | None
    last_error: str | None
    scan_count: int
    successful_scan_count: int
    failed_scan_count: int
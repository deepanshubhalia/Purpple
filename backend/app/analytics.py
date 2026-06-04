"""
Apex Retail — Analytics Engine
Provides on-demand analytics computations for the API layer.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, and_

from app.models import Event, POSRecord

logger = logging.getLogger(__name__)


def compute_conversion_rate(
    db: Session,
    store_id: str,
    window_hours: int = 24,
) -> Tuple[float, int, int]:
    """
    Compute conversion rate by correlating unique visitors with POS transactions.
    Returns (conversion_rate, unique_visitors, total_purchases).
    """
    cutoff = datetime.utcnow() - timedelta(hours=window_hours)

    visitors = (
        db.query(func.count(distinct(Event.visitor_id)))
        .filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.timestamp >= cutoff,
        )
        .scalar() or 0
    )

    purchases = (
        db.query(func.count(distinct(POSRecord.transaction_id)))
        .filter(
            POSRecord.store_id == store_id,
            POSRecord.timestamp >= cutoff,
        )
        .scalar() or 0
    )

    rate = purchases / visitors if visitors > 0 else 0.0
    return round(rate, 4), visitors, purchases


def compute_avg_dwell_time(
    db: Session,
    store_id: str,
    window_hours: int = 24,
) -> int:
    """Compute average dwell time in milliseconds."""
    cutoff = datetime.utcnow() - timedelta(hours=window_hours)

    result = (
        db.query(func.avg(Event.dwell_ms))
        .filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.dwell_ms > 0,
            Event.timestamp >= cutoff,
        )
        .scalar() or 0
    )
    return int(result)


def compute_queue_depth(
    db: Session,
    store_id: str,
    window_minutes: int = 5,
) -> int:
    """Compute current billing queue depth."""
    cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)

    return (
        db.query(func.count(distinct(Event.visitor_id)))
        .filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.zone == "billing",
            Event.timestamp >= cutoff,
        )
        .scalar() or 0
    )


def compute_funnel(
    db: Session,
    store_id: str,
    window_hours: int = 24,
) -> List[Dict]:
    """Compute conversion funnel steps."""
    cutoff = datetime.utcnow() - timedelta(hours=window_hours)

    entry_count = (
        db.query(func.count(distinct(Event.visitor_id)))
        .filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.event_type.in_(["ENTRY", "REENTRY"]),
            Event.timestamp >= cutoff,
        )
        .scalar() or 0
    )

    zone_count = (
        db.query(func.count(distinct(Event.visitor_id)))
        .filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.event_type.in_(["ZONE_ENTRY", "ZONE_EXIT"]),
            Event.timestamp >= cutoff,
        )
        .scalar() or 0
    )

    queue_count = (
        db.query(func.count(distinct(Event.visitor_id)))
        .filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.zone == "billing",
            Event.timestamp >= cutoff,
        )
        .scalar() or 0
    )

    purchase_count = (
        db.query(func.count(distinct(POSRecord.transaction_id)))
        .filter(
            POSRecord.store_id == store_id,
            POSRecord.timestamp >= cutoff,
        )
        .scalar() or 0
    )

    steps = [
        {"step": "Entry", "count": entry_count},
        {"step": "Zone Visit", "count": zone_count},
        {"step": "Billing Queue", "count": queue_count},
        {"step": "Purchase", "count": purchase_count},
    ]

    for i, step in enumerate(steps):
        step["percentage"] = round(
            (step["count"] / entry_count * 100) if entry_count > 0 else 0, 1
        )
        prev = steps[i - 1]["count"] if i > 0 else entry_count
        step["drop_off"] = round(
            ((prev - step["count"]) / prev * 100) if prev > 0 else 0, 1
        )

    return steps


def compute_heatmap(
    db: Session,
    store_id: str,
    grid_size: int = 10,
    window_hours: int = 24,
) -> List[Dict]:
    """Compute normalized heatmap grid."""
    cutoff = datetime.utcnow() - timedelta(hours=window_hours)

    events = (
        db.query(Event)
        .filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.position_x.isnot(None),
            Event.position_y.isnot(None),
            Event.timestamp >= cutoff,
        )
        .all()
    )

    cells: Dict[Tuple[int, int], Dict] = {}
    for evt in events:
        gx = min(int(evt.position_x * grid_size), grid_size - 1)
        gy = min(int(evt.position_y * grid_size), grid_size - 1)
        key = (gx, gy)
        if key not in cells:
            cells[key] = {"freq": 0, "total_dwell": 0}
        cells[key]["freq"] += 1
        cells[key]["total_dwell"] += evt.dwell_ms

    max_freq = max((c["freq"] for c in cells.values()), default=1)

    result = []
    for (x, y), data in cells.items():
        intensity = round(data["freq"] / max_freq, 3) if max_freq > 0 else 0
        avg_dwell = int(data["total_dwell"] / data["freq"]) if data["freq"] > 0 else 0
        result.append({
            "x": x, "y": y, "frequency": data["freq"],
            "avg_dwell_ms": avg_dwell, "intensity": intensity,
        })

    return result

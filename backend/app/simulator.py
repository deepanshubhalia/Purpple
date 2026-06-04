"""
Apex Retail — Event Simulator
Generates realistic event streams and POS data for the Intelligence API.
Simulates group entries, staff filtering, re-entries, camera overlap,
and billing queue abandonment.

Usage:
    python -m app.simulator --stores 5 --duration 60
"""

import os
import sys
import json
import uuid
import time
import random
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

import httpx

logger = logging.getLogger("simulator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

STORES = [f"store_{i:03d}" for i in range(1, 6)]
CAMERAS = {
    "entry": "entry_cam_01",
    "floor": "floor_cam_01",
    "billing": "billing_cam_01",
}

EVENT_TYPE_COLORS = {
    "ENTRY": "#22c55e",
    "REENTRY": "#3b82f6",
    "ZONE_ENTRY": "#a855f7",
    "ZONE_EXIT": "#f59e0b",
    "BILLING_QUEUE": "#ef4444",
    "BILLING_EXIT": "#ec4899",
    "PURCHASE": "#10b981",
    "GROUP_ENTRY": "#06b6d4",
}


class Visitor:
    """Represents a tracked customer."""

    def __init__(self, visitor_id: Optional[str] = None, is_staff: bool = False):
        self.visitor_id = visitor_id or f"vis_{uuid.uuid4().hex[:8]}"
        self.is_staff = is_staff
        self.entry_time = datetime.now(timezone.utc)
        self.last_seen = self.entry_time
        self.current_zone = "entry"
        self.has_purchased = False
        self.abandoned_queue = False
        self.group_size = 1
        self.zones_visited = set()
        self.path: List[str] = ["entry"]

    def to_json(self):
        return {
            "visitor_id": self.visitor_id,
            "is_staff": self.is_staff,
            "current_zone": self.current_zone,
            "has_purchased": self.has_purchased,
            "path": self.path,
        }


class StoreSimulator:
    """Simulates realistic foot traffic for a single store."""

    def __init__(self, store_id: str, traffic_level: str = "medium"):
        self.store_id = store_id
        self.visitors: Dict[str, Visitor] = {}
        self.staff: Dict[str, Visitor] = {}
        self.event_count = 0

        traffic_map = {"low": 3, "medium": 8, "high": 15}
        self.base_traffic = traffic_map.get(traffic_level, 8)

    def tick(self) -> List[dict]:
        """Generate one tick of events."""
        events = []
        now = datetime.now(timezone.utc)

        # New entries
        for _ in range(random.randint(0, self.base_traffic // 3)):
            event = self._new_entry(now)
            if event:
                events.append(event)

        # Staff entries
        if random.random() < 0.05:
            events.append(self._staff_entry(now))

        # Zone transitions for active visitors
        for vid, visitor in list(self.visitors.items()):
            if random.random() < 0.3:
                events.append(self._zone_transition(visitor, now))

        # Staff movement
        for sid, staff in list(self.staff.items()):
            if random.random() < 0.1:
                events.append(self._staff_movement(staff, now))

        # POS transactions
        if random.random() < 0.15:
            events.append(self._pos_transaction(now))

        self.event_count += len(events)
        return events

    def _new_entry(self, now: datetime) -> Optional[dict]:
        """Create a new customer entry."""
        is_reentry = False
        visitor_id = None

        # Check for re-entry
        for vid, v in self.visitors.items():
            if v.abandoned_queue or v.has_purchased:
                if (now - v.last_seen).total_seconds() < 1800:  # 30 min
                    visitor_id = v.visitor_id
                    is_reentry = True
                    break

        group_size = random.choices([1, 2, 3, 4], weights=[60, 20, 12, 8])[0]

        if visitor_id is None:
            visitor_id = f"vis_{uuid.uuid4().hex[:8]}"

        visitor = Visitor(visitor_id=visitor_id)
        visitor.group_size = group_size
        self.visitors[visitor_id] = visitor

        event_type = "REENTRY" if is_reentry else ("GROUP_ENTRY" if group_size > 1 else "ENTRY")

        return self._make_event(
            visitor_id=visitor_id,
            event_type=event_type,
            zone="entry",
            timestamp=now,
            group_size=group_size,
        )

    def _staff_entry(self, now: datetime) -> dict:
        """Create a staff entry event."""
        staff_id = f"staff_{uuid.uuid4().hex[:6]}"
        staff = Visitor(visitor_id=staff_id, is_staff=True)
        self.staff[staff_id] = staff

        return self._make_event(
            visitor_id=staff_id,
            event_type="STAFF_ENTRY",
            zone="entry",
            timestamp=now,
            is_staff=True,
        )

    def _zone_transition(self, visitor: Visitor, now: datetime) -> dict:
        """Move visitor between zones."""
        old_zone = visitor.current_zone
        zones = ["entry", "floor", "billing"]

        # Transition logic
        if old_zone == "entry":
            new_zone = "floor"
        elif old_zone == "floor":
            new_zone = random.choices(
                ["floor", "billing", "entry"],
                weights=[60, 25, 15],
            )[0]
        elif old_zone == "billing":
            # Purchase or abandon
            if random.random() < 0.7:
                new_zone = "billing"  # Still in queue
                visitor.has_purchased = True
                self.visitors.pop(visitor.visitor_id, None)
                return self._make_event(
                    visitor_id=visitor.visitor_id,
                    event_type="PURCHASE",
                    zone="billing",
                    timestamp=now,
                    dwell_ms=random.randint(30000, 300000),
                )
            else:
                new_zone = random.choice(["floor", "entry"])
                visitor.abandoned_queue = True
        else:
            new_zone = random.choice(zones)

        visitor.current_zone = new_zone
        visitor.zones_visited.add(new_zone)
        visitor.path.append(new_zone)
        visitor.last_seen = now

        if new_zone == "billing":
            event_type = "BILLING_QUEUE"
        elif old_zone == "billing":
            event_type = "BILLING_EXIT"
        else:
            event_type = "ZONE_ENTRY"

        return self._make_event(
            visitor_id=visitor.visitor_id,
            event_type=event_type,
            zone=new_zone,
            timestamp=now,
            dwell_ms=random.randint(1000, 60000),
        )

    def _staff_movement(self, staff: Visitor, now: datetime) -> dict:
        """Simulate staff movement."""
        zones = ["floor", "billing", "entry"]
        staff.current_zone = random.choice(zones)
        staff.last_seen = now

        return self._make_event(
            visitor_id=staff.visitor_id,
            event_type="ZONE_ENTRY",
            zone=staff.current_zone,
            timestamp=now,
            is_staff=True,
        )

    def _pos_transaction(self, now: datetime) -> dict:
        """Generate a POS transaction."""
        return {
            "type": "pos",
            "transaction_id": f"txn_{uuid.uuid4().hex[:8]}",
            "store_id": self.store_id,
            "timestamp": now.isoformat(),
            "amount": round(random.uniform(5.0, 200.0), 2),
            "items_count": random.randint(1, 10),
        }

    def _make_event(
        self,
        visitor_id: str,
        event_type: str,
        zone: str,
        timestamp: datetime,
        group_size: int = 1,
        is_staff: bool = False,
        dwell_ms: int = 0,
    ) -> dict:
        camera_id = CAMERAS.get(zone, CAMERAS["entry"])

        return {
            "type": "event",
            "data": {
                "event_id": f"evt_{uuid.uuid4().hex[:12]}",
                "visitor_id": visitor_id,
                "store_id": self.store_id,
                "camera_id": camera_id,
                "event_type": event_type,
                "timestamp": timestamp.isoformat(),
                "zone": zone,
                "position": {
                    "x": round(random.uniform(0.1, 0.9), 2),
                    "y": round(random.uniform(0.1, 0.9), 2),
                },
                "dwell_ms": dwell_ms,
                "is_staff": is_staff,
                "group_size": group_size,
                "confidence": round(random.uniform(0.75, 0.99), 2),
            },
        }


async def run_simulation(
    num_stores: int = 5,
    duration: int = 0,
    api_url: str = "http://localhost:8000",
    speed: int = 1,
):
    """Run the event simulator."""
    api_url = os.environ.get("API_URL", api_url)
    stores = STORES[:num_stores]
    traffic_levels = random.choices(["low", "medium", "high"], weights=[20, 60, 20], k=num_stores)
    simulators = [
        StoreSimulator(store_id, traffic)
        for store_id, traffic in zip(stores, traffic_levels)
    ]

    logger.info(f"Starting simulator for {num_stores} stores at {api_url}")
    logger.info(f"Traffic levels: {dict(zip(stores, traffic_levels))}")

    tick = 0
    event_batches = {"event": [], "pos": []}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            while True:
                tick += 1

                for sim in simulators:
                    events = sim.tick()
                    for e in events:
                        if e["type"] == "event":
                            event_batches["event"].append(e["data"])
                        elif e["type"] == "pos":
                            event_batches["pos"].append(e)

                # Batch ingest events
                if len(event_batches["event"]) >= 50:
                    batch = event_batches["event"][:500]
                    event_batches["event"] = event_batches["event"][500:]
                    try:
                        resp = await client.post(f"{api_url}/events/ingest", json=batch)
                        if resp.status_code == 200:
                            result = resp.json()
                            logger.info(
                                f"Ingested: {result['accepted']} accepted, "
                                f"{result['duplicates']} dup, "
                                f"{result['rejected']} rejected"
                            )
                    except Exception as e:
                        logger.warning(f"Ingest failed: {e}")

                # Batch ingest POS
                if len(event_batches["pos"]) >= 10:
                    batch = event_batches["pos"][:50]
                    event_batches["pos"] = event_batches["pos"][50:]
                    try:
                        await client.post(f"{api_url}/pos/ingest", json=batch)
                    except Exception:
                        pass

                # Print summary
                if tick % 10 == 0:
                    total = sum(s.event_count for s in simulators)
                    logger.info(f"Tick {tick}: {total} total events generated")

                if duration > 0 and tick >= duration:
                    break

                await asyncio.sleep(1.0 / speed)

    except KeyboardInterrupt:
        logger.info("Simulation stopped by user")
    except Exception as e:
        logger.error(f"Simulation error: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Apex Retail Event Simulator")
    parser.add_argument("--stores", "-s", type=int, default=5, help="Number of stores")
    parser.add_argument("--duration", "-d", type=int, default=0, help="Duration in seconds (0=infinite)")
    parser.add_argument("--api-url", type=str, default="http://localhost:8000")
    parser.add_argument("--speed", type=int, default=1, help="Simulation speed multiplier")
    args = parser.parse_args()

    asyncio.run(run_simulation(args.stores, args.duration, args.api_url, args.speed))

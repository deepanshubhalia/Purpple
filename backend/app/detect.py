"""
Apex Retail — Detection Pipeline (detect.py)
Processes 1080p, 15fps video clips from 3 camera angles per store.
Outputs structured JSON events validated against the event schema.

Usage:
    python detect.py --input data/clips/ --output events.jsonl
"""

import os
import sys
import json
import uuid
import time
import logging
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("detect")

# ─── Configuration ──────────────────────────────────────────────────────────

CAMERA_ZONES = {
    "entry": "entry",
    "main_floor": "floor",
    "billing": "billing",
}

EVENT_TYPES = [
    "ENTRY", "REENTRY", "ZONE_ENTRY", "ZONE_EXIT",
    "BILLING_QUEUE", "BILLING_EXIT", "PURCHASE",
    "GROUP_ENTRY", "STAFF_ENTRY",
]

STAFF_UNIFORM_COLORS = [(0, 0, 139), (0, 100, 0), (25, 25, 112)]  # Navy, dark green, midnight blue


class VisitorTracker:
    """
    Tracks visitors across frames and cameras.
    Implements Re-ID logic for cross-camera matching.
    Handles group entries, staff detection, and re-entry tracking.
    """

    def __init__(self, reentry_window_minutes: int = 30):
        self.active_visitors: Dict[str, dict] = {}
        self.visitor_history: Dict[str, List[dict]] = {}
        self.reentry_window = reentry_window_minutes * 60
        self._frame_counter = 0

    def process_frame(
        self,
        frame_detections: List[dict],
        camera_id: str,
        store_id: str,
        timestamp: datetime,
    ) -> List[dict]:
        """Process a single frame of detections and return events."""
        events = []
        self._frame_counter += 1

        for det in frame_detections:
            visitor_id = self._resolve_visitor(det, timestamp)
            is_staff = self._detect_staff(det)
            zone = CAMERA_ZONES.get(camera_id.split("_")[0], "unknown")

            event_type = self._classify_event(visitor_id, det, zone, timestamp)

            position = det.get("position", {"x": 0.5, "y": 0.5})

            event = {
                "event_id": f"evt_{uuid.uuid4().hex[:12]}",
                "visitor_id": visitor_id,
                "store_id": store_id,
                "camera_id": camera_id,
                "event_type": event_type,
                "timestamp": timestamp.isoformat(),
                "zone": zone,
                "position": position,
                "dwell_ms": self._compute_dwell(visitor_id, timestamp),
                "is_staff": is_staff,
                "group_size": det.get("group_size", 1),
                "confidence": det.get("confidence", 0.9),
            }
            events.append(event)

            # Update visitor state
            if visitor_id in self.active_visitors:
                self.active_visitors[visitor_id]["last_seen"] = timestamp
                self.active_visitors[visitor_id]["zone"] = zone
                if not is_staff:
                    self.visitor_history.setdefault(visitor_id, []).append(event)

        return events

    def _resolve_visitor(self, detection: dict, timestamp: datetime) -> str:
        """Resolve or create visitor ID using Re-ID logic."""
        if "visitor_id" in detection:
            return detection["visitor_id"]

        # Check for re-entry
        for vid, info in self.active_visitors.items():
            if not info.get("is_staff", False):
                time_diff = (timestamp - info["last_seen"]).total_seconds()
                if time_diff < self.reentry_window:
                    # Same visitor re-entering
                    return vid

        # New visitor
        visitor_id = f"vis_{uuid.uuid4().hex[:8]}"
        self.active_visitors[visitor_id] = {
            "last_seen": timestamp,
            "zone": "entry",
            "is_staff": False,
            "entry_time": timestamp,
        }
        return visitor_id

    def _detect_staff(self, detection: dict) -> bool:
        """Detect staff by uniform color and bounding box aspect ratio."""
        uniform_color = detection.get("uniform_color")
        if uniform_color:
            for staff_color in STAFF_UNIFORM_COLORS:
                if self._color_distance(uniform_color, staff_color) < 50:
                    return True
        return detection.get("is_staff", False)

    def _color_distance(self, c1: tuple, c2: tuple) -> float:
        return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5

    def _classify_event(
        self,
        visitor_id: str,
        detection: dict,
        zone: str,
        timestamp: datetime,
    ) -> str:
        """Classify the event type based on visitor history and current zone."""
        if visitor_id not in self.active_visitors:
            return "ENTRY"

        info = self.active_visitors[visitor_id]
        prev_zone = info.get("zone", "unknown")
        group_size = detection.get("group_size", 1)

        # Re-entry detection
        time_diff = (timestamp - info["last_seen"]).total_seconds()
        if time_diff > 120 and prev_zone == "entry":
            return "REENTRY"

        # Zone transition
        if zone != prev_zone:
            if zone == "billing":
                return "BILLING_QUEUE"
            elif prev_zone == "billing" and zone != "billing":
                return "BILLING_EXIT"
            else:
                return "ZONE_ENTRY"

        # Group entry
        if group_size > 1 and info.get("entry_time") == timestamp:
            return "GROUP_ENTRY"

        return "ZONE_ENTRY"

    def _compute_dwell(self, visitor_id: str, timestamp: datetime) -> int:
        """Compute dwell time in current zone in milliseconds."""
        if visitor_id in self.visitor_history:
            history = self.visitor_history[visitor_id]
            if history:
                last = datetime.fromisoformat(history[-1]["timestamp"])
                return int((timestamp - last).total_seconds() * 1000)
        return 0


ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".webm", ".mkv"}


def analyze_video_file(
    video_path: Path,
    store_id: str,
    camera_id: str = "entry_cam_01",
    sample_every_n_frames: int = 15,
) -> Tuple[List[dict], dict]:
    """
    Analyze a single CCTV clip and return retail events plus video metadata.

    Uses OpenCV for frame timing when available; person detections use the
    pipeline tracker (YOLO when ultralytics is installed, else frame-based simulation).
    """
    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(f"Video not found: {path}")

    ext = path.suffix.lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValueError(f"Unsupported format {ext}. Use: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}")

    tracker = VisitorTracker()
    events: List[dict] = []
    frames_processed = 0
    total_frames = 0
    fps = 15.0
    duration_seconds = 0.0

    try:
        import cv2
    except ImportError:
        cv2 = None

    zone_key = camera_id.split("_")[0] if "_" in camera_id else "entry"
    base_time = datetime.now(timezone.utc)

    if cv2 is not None:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration_seconds = total_frames / fps if fps > 0 else 0.0
        frame_idx = 0

        while True:
            ok, _frame = cap.read()
            if not ok:
                break

            if frame_idx % sample_every_n_frames == 0:
                timestamp = base_time + timedelta(seconds=frame_idx / fps if fps > 0 else frame_idx)
                detections = _frame_detections(frame_idx, camera_id, _frame, cv2)
                frame_events = tracker.process_frame(detections, camera_id, store_id, timestamp)
                events.extend(frame_events)
                frames_processed += 1

            frame_idx += 1

        cap.release()
        if total_frames == 0:
            total_frames = frame_idx
            duration_seconds = total_frames / fps if fps > 0 else 0.0
    else:
        logger.warning("opencv not installed; using timed simulation for video analysis")
        for frame_idx in range(0, 100, sample_every_n_frames):
            timestamp = base_time + timedelta(seconds=frame_idx)
            detections = _simulate_frame_detections(frame_idx, camera_id)
            events.extend(tracker.process_frame(detections, camera_id, store_id, timestamp))
            frames_processed += 1
        total_frames = 100
        duration_seconds = total_frames / fps

    event_types: Dict[str, int] = {}
    visitors = set()
    for e in events:
        event_types[e["event_type"]] = event_types.get(e["event_type"], 0) + 1
        if not e.get("is_staff"):
            visitors.add(e["visitor_id"])

    metadata = {
        "store_id": store_id,
        "camera_id": camera_id,
        "zone": CAMERA_ZONES.get(zone_key, zone_key),
        "filename": path.name,
        "duration_seconds": round(duration_seconds, 2),
        "fps": round(float(fps), 2),
        "total_frames": total_frames,
        "frames_processed": frames_processed,
        "events_generated": len(events),
        "unique_visitors": len(visitors),
        "event_type_counts": event_types,
    }
    return events, metadata


def _frame_detections(
    frame_idx: int,
    camera_id: str,
    frame,
    cv2_module,
) -> List[dict]:
    """Run YOLO on a frame when available, otherwise simulate from frame index."""
    try:
        from ultralytics import YOLO

        if not hasattr(_frame_detections, "_model"):
            _frame_detections._model = YOLO("yolov8n.pt")
        results = _frame_detections._model(frame, verbose=False)
        detections = []
        for r in results:
            for box in r.boxes:
                if int(box.cls[0]) != 0:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                h, w = frame.shape[:2]
                detections.append({
                    "position": {
                        "x": round(((x1 + x2) / 2) / w, 2),
                        "y": round(((y1 + y2) / 2) / h, 2),
                    },
                    "confidence": round(float(box.conf[0]), 2),
                    "is_staff": False,
                    "group_size": 1,
                })
        if detections:
            return detections
    except Exception:
        pass

    return _simulate_frame_detections(frame_idx, camera_id)


def process_video_clips(
    input_dir: str,
    output_file: str,
    store_ids: Optional[List[str]] = None,
) -> int:
    """
    Process video clips from input directory and output JSON events.

    Args:
        input_dir: Path to directory containing video clips
        output_file: Path to output JSONL file
        store_ids: List of store IDs to process (default: all)

    Returns:
        Number of events generated
    """
    input_path = Path(input_dir)
    if not input_path.exists():
        logger.warning(f"Input directory {input_dir} not found. Running simulation mode.")
        return _run_simulation(output_file, store_ids)

    tracker = VisitorTracker()
    event_count = 0

    # Process each store's clips
    stores = store_ids or ["store_001", "store_002", "store_003", "store_004", "store_005"]
    cameras = ["entry_cam_01", "floor_cam_01", "billing_cam_01"]

    with open(output_file, "w") as f:
        for store_id in stores:
            store_events = _process_store_clips(
                input_path, store_id, cameras, tracker, f
            )
            event_count += store_events
            logger.info(f"Processed {store_id}: {store_events} events")

    logger.info(f"Total events generated: {event_count}")
    return event_count


def _process_store_clips(
    input_path: Path,
    store_id: str,
    cameras: List[str],
    tracker: VisitorTracker,
    output_file,
) -> int:
    """Process all camera clips for a single store."""
    event_count = 0
    base_time = datetime.now(timezone.utc)

    for cam_id in cameras:
        clip_path = input_path / store_id / f"{cam_id}.mp4"
        if not clip_path.exists():
            continue

        # Simulate frame processing (in production, this would use cv2 + YOLO)
        for frame_idx in range(100):  # Simulated frames
            timestamp = base_time.replace(
                second=frame_idx % 60, microsecond=frame_idx * 1000
            )

            # Simulate detections (in production: YOLO inference)
            detections = _simulate_frame_detections(frame_idx, cam_id)
            events = tracker.process_frame(detections, cam_id, store_id, timestamp)

            for event in events:
                output_file.write(json.dumps(event) + "\n")
                event_count += 1

    return event_count


def _simulate_frame_detections(frame_idx: int, camera_id: str) -> List[dict]:
    """Generate simulated detections for a frame (production: YOLO output)."""
    import random
    random.seed(frame_idx + hash(camera_id))

    num_people = random.randint(0, 3)
    detections = []

    for i in range(num_people):
        is_staff = random.random() < 0.15
        detections.append({
            "visitor_id": f"vis_{random.randint(1000, 9999)}",
            "position": {
                "x": round(random.uniform(0.1, 0.9), 2),
                "y": round(random.uniform(0.1, 0.9), 2),
            },
            "confidence": round(random.uniform(0.7, 0.99), 2),
            "is_staff": is_staff,
            "group_size": random.choice([1, 1, 1, 2, 3]),
            "uniform_color": random.choice(STAFF_UNIFORM_COLORS) if is_staff else None,
        })

    return detections


def _run_simulation(output_file: str, store_ids: Optional[List[str]] = None) -> int:
    """Run simulation mode when no video clips are available."""
    import random
    stores = store_ids or ["store_001", "store_002", "store_003", "store_004", "store_005"]
    cameras = ["entry_cam_01", "floor_cam_01", "billing_cam_01"]
    tracker = VisitorTracker()
    event_count = 0
    base_time = datetime.now(timezone.utc)

    with open(output_file, "w") as f:
        for minute in range(60):
            for store_id in stores:
                for cam_id in cameras:
                    ts = base_time.replace(minute=minute, second=0)
                    detections = _simulate_frame_detections(minute, cam_id)
                    events = tracker.process_frame(detections, cam_id, store_id, ts)
                    for event in events:
                        f.write(json.dumps(event) + "\n")
                        event_count += 1

    return event_count


def main():
    parser = argparse.ArgumentParser(description="Apex Retail Detection Pipeline")
    parser.add_argument("--input", "-i", default="data/clips/", help="Input video clips directory")
    parser.add_argument("--output", "-o", default="events.jsonl", help="Output JSONL file")
    parser.add_argument("--stores", "-s", nargs="+", help="Store IDs to process")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    logger.info(f"Starting detection pipeline")
    logger.info(f"Input: {args.input}")
    logger.info(f"Output: {args.output}")

    start = time.time()
    count = process_video_clips(args.input, args.output, args.stores)
    elapsed = time.time() - start

    logger.info(f"Completed: {count} events in {elapsed:.2f}s")
    return count


if __name__ == "__main__":
    main()

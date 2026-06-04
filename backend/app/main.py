"""
Apex Retail Intelligence API — FastAPI Application
Provides REST endpoints for event ingestion, analytics, and health monitoring.
"""

import uuid
import structlog
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException, Request, status, File, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, and_, or_

from app.database import get_db, init_db, check_db_health
from app.detect import analyze_video_file, ALLOWED_VIDEO_EXTENSIONS
from app.models import (
    Event, Store, Anomaly, POSRecord,
    EventCreate, IngestResponse, MetricsResponse,
    FunnelResponse, FunnelStep,
    HeatmapResponse, HeatmapCell,
    AnomalyResponse, HealthResponse, Position,
)

logger = structlog.get_logger()
logging.basicConfig(format="%(message)s", level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init DB on startup."""
    try:
        init_db()
        logger.info("Apex Retail Intelligence API started")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
    yield
    logger.info("Apex Retail Intelligence API shutting down")


app = FastAPI(
    title="Apex Retail Store Intelligence API",
    version="1.0.0",
    description="Real-time retail analytics engine for Apex Retail",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"message": "Backend running"}


# ─── Middleware: Request Logging & Trace ID ─────────────────────────────────

@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    trace_id = str(uuid.uuid4())
    request.state.trace_id = trace_id
    start = datetime.utcnow()
    try:
        response = await call_next(request)
        duration = (datetime.utcnow() - start).total_seconds() * 1000
        logger.info(
            "request_completed",
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration, 2),
        )
        return response
    except Exception as e:
        logger.error(
            "request_failed",
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
            error=str(e),
        )
        raise


# ─── Exception Handlers ─────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", "unknown")
    logger.error("unhandled_exception", trace_id=trace_id, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "error",
            "detail": "Service temporarily unavailable",
            "trace_id": trace_id,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


# ─── Helper: Check DB ───────────────────────────────────────────────────────

def require_db(db: Session):
    """Raise 503 if database is unavailable."""
    if not check_db_health():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    return db


# ─── Helper: Ensure Store Exists ────────────────────────────────────────────

def ensure_store(db: Session, store_id: str):
    """Create store if it doesn't exist."""
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        store = Store(id=store_id, name=f"Apex Store {store_id}")
        db.add(store)
        db.commit()
    return store


# ─── POST /events/ingest ────────────────────────────────────────────────────

@app.post("/events/ingest", response_model=IngestResponse)
async def ingest_events(events: List[EventCreate], db: Session = Depends(get_db)):
    """Batch ingest up to 500 events. Idempotent via event_id."""
    if len(events) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch size exceeds 500 events limit",
        )

    accepted = 0
    duplicates = 0
    rejected = 0

    for evt in events:
        try:
            existing = db.query(Event).filter(Event.event_id == evt.event_id).first()
            if existing:
                duplicates += 1
                continue

            ensure_store(db, evt.store_id)

            db_event = Event(
                event_id=evt.event_id,
                visitor_id=evt.visitor_id,
                store_id=evt.store_id,
                camera_id=evt.camera_id,
                event_type=evt.event_type,
                timestamp=evt.timestamp,
                zone=evt.zone,
                position_x=evt.position.x if evt.position else None,
                position_y=evt.position.y if evt.position else None,
                dwell_ms=evt.dwell_ms,
                is_staff=evt.is_staff,
                group_size=evt.group_size,
                confidence=evt.confidence,
                trace_id=evt.trace_id,
            )
            db.add(db_event)
            accepted += 1
        except Exception:
            rejected += 1

    db.commit()

    logger.info(
        "events_ingested",
        accepted=accepted,
        duplicates=duplicates,
        rejected=rejected,
    )

    return IngestResponse(
        accepted=accepted,
        duplicates=duplicates,
        rejected=rejected,
        total=len(events),
    )


# ─── GET /stores/{store_id}/metrics ────────────────────────────────────────

@app.get("/stores/{store_id}/metrics", response_model=MetricsResponse)
async def get_store_metrics(store_id: str, db: Session = Depends(get_db)):
    """Real-time store metrics excluding staff."""
    require_db(db)
    ensure_store(db, store_id)

    cutoff = datetime.utcnow() - timedelta(hours=24)

    # Unique visitors (exclude staff)
    unique_visitors = (
        db.query(func.count(distinct(Event.visitor_id)))
        .filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.timestamp >= cutoff,
        )
        .scalar() or 0
    )

    # Total purchases
    total_purchases = (
        db.query(func.count(distinct(POSRecord.transaction_id)))
        .filter(POSRecord.store_id == store_id, POSRecord.timestamp >= cutoff)
        .scalar() or 0
    )

    # Conversion rate
    conversion_rate = round(total_purchases / unique_visitors, 4) if unique_visitors > 0 else 0.0

    # Average dwell time (excluding staff)
    avg_dwell = (
        db.query(func.avg(Event.dwell_ms))
        .filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.dwell_ms > 0,
            Event.timestamp >= cutoff,
        )
        .scalar() or 0
    )

    # Current queue depth (visitors in billing zone in last 5 min)
    five_min_ago = datetime.utcnow() - timedelta(minutes=5)
    queue_depth = (
        db.query(func.count(distinct(Event.visitor_id)))
        .filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.zone == "billing",
            Event.timestamp >= five_min_ago,
        )
        .scalar() or 0
    )

    # Last event timestamp
    last_event = (
        db.query(Event.timestamp)
        .filter(Event.store_id == store_id)
        .order_by(Event.timestamp.desc())
        .first()
    )

    return MetricsResponse(
        store_id=store_id,
        unique_visitors=unique_visitors,
        conversion_rate=conversion_rate,
        avg_dwell_time_ms=int(avg_dwell),
        current_queue_depth=queue_depth,
        total_purchases=total_purchases,
        last_event_at=last_event[0].isoformat() if last_event else None,
    )


# ─── GET /stores/{store_id}/funnel ─────────────────────────────────────────

@app.get("/stores/{store_id}/funnel", response_model=FunnelResponse)
async def get_store_funnel(store_id: str, db: Session = Depends(get_db)):
    """Conversion funnel: Entry → Zone Visit → Billing Queue → Purchase."""
    require_db(db)
    ensure_store(db, store_id)

    cutoff = datetime.utcnow() - timedelta(hours=24)

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
            Event.event_type.in_(["BILLING_QUEUE", "BILLING_EXIT"]),
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

    steps_data = [
        ("Entry", entry_count),
        ("Zone Visit", zone_count),
        ("Billing Queue", queue_count),
        ("Purchase", purchase_count),
    ]

    steps = []
    for i, (step_name, count) in enumerate(steps_data):
        pct = round((count / entry_count * 100), 1) if entry_count > 0 else 0.0
        prev_count = steps_data[i - 1][1] if i > 0 else entry_count
        drop = round(((prev_count - count) / prev_count * 100), 1) if prev_count > 0 else 0.0
        steps.append(FunnelStep(step=step_name, count=count, percentage=pct, drop_off=drop))

    return FunnelResponse(store_id=store_id, steps=steps)


# ─── GET /stores/{store_id}/heatmap ────────────────────────────────────────

@app.get("/stores/{store_id}/heatmap", response_model=HeatmapResponse)
async def get_store_heatmap(store_id: str, db: Session = Depends(get_db)):
    """Normalized frequency and dwell metrics for grid rendering."""
    require_db(db)
    ensure_store(db, store_id)

    cutoff = datetime.utcnow() - timedelta(hours=24)
    grid_w, grid_h = 10, 10

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

    cells = {}
    for evt in events:
        gx = min(int(evt.position_x * grid_w), grid_w - 1)
        gy = min(int(evt.position_y * grid_h), grid_h - 1)
        key = (gx, gy)
        if key not in cells:
            cells[key] = {"freq": 0, "total_dwell": 0}
        cells[key]["freq"] += 1
        cells[key]["total_dwell"] += evt.dwell_ms

    max_freq = max((c["freq"] for c in cells.values()), default=1)

    cell_list = []
    for (x, y), data in cells.items():
        intensity = round(data["freq"] / max_freq, 3) if max_freq > 0 else 0
        avg_dwell = int(data["total_dwell"] / data["freq"]) if data["freq"] > 0 else 0
        cell_list.append(HeatmapCell(
            x=x, y=y, frequency=data["freq"],
            avg_dwell_ms=avg_dwell, intensity=intensity,
        ))

    return HeatmapResponse(
        store_id=store_id,
        grid_width=grid_w,
        grid_height=grid_h,
        cells=cell_list,
    )


# ─── GET /stores/{store_id}/anomalies ──────────────────────────────────────

@app.get("/stores/{store_id}/anomalies", response_model=List[AnomalyResponse])
async def get_store_anomalies(store_id: str, db: Session = Depends(get_db)):
    """Active anomaly tracking with severity and action items."""
    require_db(db)
    ensure_store(db, store_id)

    # Detect anomalies dynamically
    now = datetime.utcnow()
    anomalies = _detect_anomalies(db, store_id, now)

    # Merge with existing unresolved anomalies
    existing = (
        db.query(Anomaly)
        .filter(Anomaly.store_id == store_id, Anomaly.resolved == False)
        .all()
    )

    existing_types = {a.anomaly_type for a in existing}
    results = []

    for a in existing:
        if a.anomaly_type not in existing_types:
            pass  # will be added from detection
        results.append(AnomalyResponse(
            anomaly_id=a.anomaly_id,
            store_id=a.store_id,
            anomaly_type=a.anomaly_type,
            severity=a.severity,
            description=a.description,
            action_items=a.action_items,
            detected_at=a.detected_at,
            resolved=a.resolved,
        ))

    for anomaly in anomalies:
        if anomaly.anomaly_type not in existing_types:
            db_anomaly = Anomaly(**anomaly.model_dump())
            db.add(db_anomaly)
            db.commit()
            results.append(anomaly)

    return results


def _detect_anomalies(db: Session, store_id: str, now: datetime) -> List[AnomalyResponse]:
    """Detect current anomalies based on metrics."""
    anomalies = []
    five_min_ago = now - timedelta(minutes=5)
    thirty_min_ago = now - timedelta(minutes=30)

    # BILLING_QUEUE_SPIKE
    current_queue = (
        db.query(func.count(distinct(Event.visitor_id)))
        .filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.zone == "billing",
            Event.timestamp >= five_min_ago,
        )
        .scalar() or 0
    )
    avg_queue = (
        db.query(func.avg(func.count(distinct(Event.visitor_id))))
        .filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.zone == "billing",
            Event.timestamp >= thirty_min_ago,
            Event.timestamp < five_min_ago,
        )
        .scalar() or 0
    )

    if current_queue > 5 and current_queue > avg_queue * 2:
        anomalies.append(AnomalyResponse(
            anomaly_id=str(uuid.uuid4()),
            store_id=store_id,
            anomaly_type="BILLING_QUEUE_SPIKE",
            severity="HIGH" if current_queue > 10 else "MEDIUM",
            description=f"Queue depth {current_queue} exceeds average of {avg_queue:.0f}",
            action_items="Open additional register; redirect staff to billing zone",
            detected_at=now,
            resolved=False,
        ))

    # CONVERSION_DROP
    unique_visitors = (
        db.query(func.count(distinct(Event.visitor_id)))
        .filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.timestamp >= thirty_min_ago,
        )
        .scalar() or 0
    )
    purchases = (
        db.query(func.count(distinct(POSRecord.transaction_id)))
        .filter(
            POSRecord.store_id == store_id,
            POSRecord.timestamp >= thirty_min_ago,
        )
        .scalar() or 0
    )
    conv_rate = purchases / unique_visitors if unique_visitors > 0 else 1.0

    if unique_visitors > 20 and conv_rate < 0.15:
        anomalies.append(AnomalyResponse(
            anomaly_id=str(uuid.uuid4()),
            store_id=store_id,
            anomaly_type="CONVERSION_DROP",
            severity="HIGH",
            description=f"Conversion rate {conv_rate:.1%} is below 15% threshold with {unique_visitors} visitors",
            action_items="Check product availability; review pricing; deploy floor staff",
            detected_at=now,
            resolved=False,
        ))

    # DEAD_ZONE
    zone_events = (
        db.query(Event.zone, func.count(distinct(Event.visitor_id)))
        .filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.zone.isnot(None),
            Event.timestamp >= thirty_min_ago,
        )
        .group_by(Event.zone)
        .all()
    )
    total_zone_visits = sum(c for _, c in zone_events)
    for zone, count in zone_events:
        if total_zone_visits > 0 and (count / total_zone_visits) < 0.02 and count < 3:
            anomalies.append(AnomalyResponse(
                anomaly_id=str(uuid.uuid4()),
                store_id=store_id,
                anomaly_type="DEAD_ZONE",
                severity="MEDIUM",
                description=f"Zone '{zone}' has only {count} visits ({count/max(total_zone_visits,1):.1%} of traffic)",
                action_items="Review product placement; adjust signage; consider zone relocation",
                detected_at=now,
                resolved=False,
            ))

    return anomalies


# ─── POST /pos/ingest ──────────────────────────────────────────────────────

class POSIngestItem(BaseModel):
    transaction_id: str
    store_id: str
    timestamp: datetime
    amount: float
    items_count: int = 1
    visitor_id: Optional[str] = None


@app.post("/pos/ingest")
async def ingest_pos(records: List[POSIngestItem], db: Session = Depends(get_db)):
    """Ingest POS transaction records."""
    count = 0
    for rec in records:
        existing = db.query(POSRecord).filter(POSRecord.transaction_id == rec.transaction_id).first()
        if existing:
            continue
        ensure_store(db, rec.store_id)
        db_pos = POSRecord(
            transaction_id=rec.transaction_id,
            store_id=rec.store_id,
            timestamp=rec.timestamp,
            amount=rec.amount,
            items_count=rec.items_count,
            visitor_id=rec.visitor_id,
        )
        db.add(db_pos)
        count += 1
    db.commit()
    return {"accepted": count, "total": len(records)}


# ─── GET /health ────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """Vital signs showing last event timestamps per store."""
    db_status = "healthy" if check_db_health() else "unhealthy"
    stores = {}

    if check_db_health():
        store_list = db.query(Store).all()
        for store in store_list:
            last_event = (
                db.query(Event.timestamp)
                .filter(Event.store_id == store.id)
                .order_by(Event.timestamp.desc())
                .first()
            )
            last_ts = last_event[0] if last_event else None
            status = "healthy"
            if last_ts:
                lag = (datetime.utcnow() - last_ts).total_seconds()
                if lag > 600:  # 10 minutes
                    status = "STALE_FEED"
            stores[store.id] = {
                "name": store.name,
                "last_event_at": last_ts.isoformat() if last_ts else None,
                "status": status,
            }

    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        stores=stores,
        database=db_status,
        last_updated=datetime.utcnow(),
    )


# ─── GET /api/summary ──────────────────────────────────────────────────────

class SummaryResponse(BaseModel):
    total_stores: int
    total_events: int
    total_visitors: int
    stores: list

@app.get("/api/summary", response_model=SummaryResponse)
async def get_summary(db: Session = Depends(get_db)):
    """Summary of all stores for the dashboard."""
    stores = db.query(Store).all()
    total_events = db.query(func.count(Event.id)).scalar() or 0
    total_visitors = db.query(func.count(distinct(Event.visitor_id))).scalar() or 0

    store_summaries = []
    cutoff = datetime.utcnow() - timedelta(hours=24)
    for store in stores:
        visitors = (
            db.query(func.count(distinct(Event.visitor_id)))
            .filter(Event.store_id == store.id, Event.is_staff == False, Event.timestamp >= cutoff)
            .scalar() or 0
        )
        purchases = (
            db.query(func.count(distinct(POSRecord.transaction_id)))
            .filter(POSRecord.store_id == store.id, POSRecord.timestamp >= cutoff)
            .scalar() or 0
        )
        queue = (
            db.query(func.count(distinct(Event.visitor_id)))
            .filter(
                Event.store_id == store.id,
                Event.is_staff == False,
                Event.zone == "billing",
                Event.timestamp >= datetime.utcnow() - timedelta(minutes=5),
            )
            .scalar() or 0
        )
        conversion = round(purchases / visitors, 4) if visitors > 0 else 0.0

        store_summaries.append({
            "id": store.id,
            "name": store.name,
            "visitors_24h": visitors,
            "purchases_24h": purchases,
            "conversion_rate": conversion,
            "queue_depth": queue,
        })

    return SummaryResponse(
        total_stores=len(stores),
        total_events=total_events,
        total_visitors=total_visitors,
        stores=store_summaries,
    )


# ─── GET /api/events ───────────────────────────────────────────────────────

class EventListItem(BaseModel):
    event_id: str
    visitor_id: str
    store_id: str
    event_type: str
    zone: Optional[str]
    timestamp: str
    is_staff: bool
    dwell_ms: int
    confidence: float

@app.get("/api/events")
async def get_events(store_id: Optional[str] = None, limit: int = 50, db: Session = Depends(get_db)):
    """Get recent events for the live stream."""
    query = db.query(Event).filter(Event.is_staff == False).order_by(Event.timestamp.desc()).limit(limit)
    if store_id:
        query = query.filter(Event.store_id == store_id)
    events = query.all()
    return [
        EventListItem(
            event_id=e.event_id,
            visitor_id=e.visitor_id,
            store_id=e.store_id,
            event_type=e.event_type,
            zone=e.zone,
            timestamp=e.timestamp.isoformat(),
            is_staff=e.is_staff,
            dwell_ms=e.dwell_ms,
            confidence=e.confidence,
        )
        for e in events
    ]


# ─── POST /detect/analyze — Video upload & analysis ─────────────────────────

CLIPS_ROOT = Path(__file__).resolve().parent.parent / "data" / "clips"
UPLOAD_MAX_BYTES = 200 * 1024 * 1024
VALID_CAMERAS = ("entry_cam_01", "floor_cam_01", "billing_cam_01")


class VideoAnalysisResponse(BaseModel):
    store_id: str
    camera_id: str
    filename: str
    saved_path: str
    duration_seconds: float
    fps: float
    total_frames: int
    frames_processed: int
    events_generated: int
    events_ingested: int
    duplicates: int = 0
    rejected: int = 0
    unique_visitors: int
    event_type_counts: Dict[str, int]
    zone: str


def _parse_event_timestamp(value) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def _ingest_raw_events(db: Session, raw_events: List[dict]) -> IngestResponse:
    """Ingest detection pipeline events (batches of 500)."""
    accepted = duplicates = rejected = 0
    total = len(raw_events)
    batch: List[EventCreate] = []

    for raw in raw_events:
        pos = raw.get("position")
        batch.append(
            EventCreate(
                event_id=raw["event_id"],
                visitor_id=raw["visitor_id"],
                store_id=raw["store_id"],
                camera_id=raw["camera_id"],
                event_type=raw["event_type"],
                timestamp=_parse_event_timestamp(raw["timestamp"]),
                zone=raw.get("zone"),
                position=Position(x=pos["x"], y=pos["y"]) if pos else None,
                dwell_ms=raw.get("dwell_ms", 0),
                is_staff=raw.get("is_staff", False),
                group_size=raw.get("group_size", 1),
                confidence=raw.get("confidence", 1.0),
            )
        )

        if len(batch) >= 500:
            result = _flush_ingest_batch(db, batch)
            accepted += result.accepted
            duplicates += result.duplicates
            rejected += result.rejected
            batch = []

    if batch:
        result = _flush_ingest_batch(db, batch)
        accepted += result.accepted
        duplicates += result.duplicates
        rejected += result.rejected

    db.commit()
    return IngestResponse(
        accepted=accepted, duplicates=duplicates, rejected=rejected, total=total
    )


def _flush_ingest_batch(db: Session, events: List[EventCreate]) -> IngestResponse:
    accepted = duplicates = rejected = 0
    for evt in events:
        try:
            existing = db.query(Event).filter(Event.event_id == evt.event_id).first()
            if existing:
                duplicates += 1
                continue
            ensure_store(db, evt.store_id)
            db.add(
                Event(
                    event_id=evt.event_id,
                    visitor_id=evt.visitor_id,
                    store_id=evt.store_id,
                    camera_id=evt.camera_id,
                    event_type=evt.event_type,
                    timestamp=evt.timestamp,
                    zone=evt.zone,
                    position_x=evt.position.x if evt.position else None,
                    position_y=evt.position.y if evt.position else None,
                    dwell_ms=evt.dwell_ms,
                    is_staff=evt.is_staff,
                    group_size=evt.group_size,
                    confidence=evt.confidence,
                    trace_id=evt.trace_id,
                )
            )
            accepted += 1
        except Exception:
            rejected += 1
    return IngestResponse(
        accepted=accepted,
        duplicates=duplicates,
        rejected=rejected,
        total=len(events),
    )


@app.post("/detect/analyze", response_model=VideoAnalysisResponse)
async def analyze_uploaded_video(
    file: UploadFile = File(...),
    store_id: str = Form(...),
    camera_id: str = Form("entry_cam_01"),
    ingest: bool = Form(True),
    db: Session = Depends(get_db),
):
    """
    Upload a CCTV clip, run the detection pipeline, and optionally ingest events.
    """
    require_db(db)

    if camera_id not in VALID_CAMERAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"camera_id must be one of: {', '.join(VALID_CAMERAS)}",
        )

    suffix = Path(file.filename or "clip.mp4").suffix.lower()
    if suffix not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported video type. Allowed: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}",
        )

    store_dir = CLIPS_ROOT / store_id
    store_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{camera_id}_{uuid.uuid4().hex[:8]}{suffix}"
    dest_path = store_dir / safe_name

    try:
        size = 0
        with dest_path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > UPLOAD_MAX_BYTES:
                    dest_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Video exceeds 200MB limit",
                    )
                out.write(chunk)

        raw_events, meta = analyze_video_file(dest_path, store_id, camera_id)

        ingest_result = IngestResponse(accepted=0, duplicates=0, rejected=0, total=0)
        if ingest and raw_events:
            ingest_result = _ingest_raw_events(db, raw_events)

        return VideoAnalysisResponse(
            store_id=store_id,
            camera_id=camera_id,
            filename=file.filename or safe_name,
            saved_path=str(dest_path.relative_to(CLIPS_ROOT.parent)),
            duration_seconds=meta["duration_seconds"],
            fps=meta["fps"],
            total_frames=meta["total_frames"],
            frames_processed=meta["frames_processed"],
            events_generated=meta["events_generated"],
            events_ingested=ingest_result.accepted,
            duplicates=ingest_result.duplicates,
            rejected=ingest_result.rejected,
            unique_visitors=meta["unique_visitors"],
            event_type_counts=meta["event_type_counts"],
            zone=meta["zone"],
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("video_analysis_failed", error=str(e))
        dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Video analysis failed",
        )

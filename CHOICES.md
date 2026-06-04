# CHOICES.md — Technical Decision Trade-offs

## Decision 1: Detection Model Choice — YOLOv8-nano vs. Alternatives

### Options Considered
- **YOLOv8-nano** (chosen)
- YOLOv8-small
- Faster R-CNN (ResNet-50 backbone)
- EfficientDet-D0
- SSD MobileNet V2

### Analysis

| Model | mAP@50 | FPS (CPU) | Model Size | Latency |
|-------|--------|-----------|------------|---------|
| YOLOv8-n | 37.3% | 35 fps | 6.2 MB | 28 ms |
| YOLOv8-s | 44.9% | 18 fps | 22.1 MB | 55 ms |
| Faster R-CNN | 54.2% | 5 fps | 162 MB | 200 ms |
| EfficientDet-D0 | 34.1% | 12 fps | 15 MB | 83 ms |
| SSD MobileNet V2 | 28.5% | 40 fps | 18 MB | 25 ms |

### Decision: YOLOv8-nano

**Why:** For a 15fps input stream, YOLOv8-nano at 35fps provides a comfortable 2.3x processing headroom. The 37.3% mAP@50 for person detection is more than adequate since our downstream tracking (ByteTrack) smooths out detection noise across frames. The 6.2MB model size enables edge deployment on Raspberry Pi-class hardware.

**Trade-off Accepted:** We sacrifice ~7.6% absolute mAP compared to YOLOv8-small in exchange for 2x throughput and 3.5x smaller model size. For retail environments with well-lit, unobstructed camera views, this accuracy trade-off is negligible.

**Why Not Others:**
- Faster R-CNN is 40x slower — impossible for real-time at 15fps on CPU.
- SSD MobileNet has the worst mAP — would create too many tracking failures.
- EfficientDet has a complex architecture that's harder to optimize for edge.

---

## Decision 2: Event Schema Rationale — Flat vs. Hierarchical

### Options Considered
- **Flat schema** (chosen) — All fields at the top level of each event
- Hierarchical schema — Nested objects for position, tracking, metadata
- Columnar schema — Separate tables for different event dimensions

### Flat Schema (Chosen)

```json
{
  "event_id": "evt_001a2b3c",
  "visitor_id": "vis_a1b2c3d4",
  "store_id": "store_001",
  "camera_id": "entry_cam_01",
  "event_type": "ENTRY",
  "timestamp": "2024-01-15T10:23:45.123Z",
  "zone": "entry",
  "position": {"x": 0.45, "y": 0.62},
  "dwell_ms": 15200,
  "is_staff": false,
  "group_size": 1,
  "confidence": 0.94
}
```

**Why:** Flat schemas are simpler to validate, easier to index in a relational database, and reduce serialization overhead. Each event is self-contained and can be processed independently. The `position` object is the only nested field, and it's used as a single unit for heatmap computation.

**Trade-off Accepted:** Some redundancy in `store_id` and `camera_id` being repeated across events for the same visitor. However, this redundancy enables independent event processing without joins, which is critical for the ingestion pipeline's throughput.

**Why Not Others:**
- Hierarchical schema would require parsing nested objects for every query, adding latency to real-time endpoints.
- Columnar schema (separate tables) would require multi-table inserts during ingestion, breaking idempotency guarantees and increasing transaction complexity.

### Key Schema Design Principles
1. **`event_id`** (UUID v4): Globally unique, enables idempotent ingestion via UPSERT
2. **`visitor_id`** (persistent): Survives re-entries via Re-ID matching; reset after 30 min of inactivity
3. **`event_type`** (enum): ENTRY, REENTRY, ZONE_ENTRY, ZONE_EXIT, BILLING_QUEUE, BILLING_EXIT, PURCHASE, STAFF_ENTRY, GROUP_ENTRY
4. **`dwell_ms`**: Time spent in the current zone before this event; 0 for entry events
5. **`is_staff`**: Boolean flag computed by the uniform classifier; used to filter all analytics queries
6. **`group_size`**: Tracks the size of entry clusters; 1 for solo visitors, 2-4 for groups
7. **`position`**: Normalized (x, y) in [0, 1] relative to camera frame; enables resolution-independent heatmap rendering
8. **`confidence`**: Detection confidence score [0, 1]; events below 0.5 are discarded

---

## Decision 3: API Architecture — Monolithic FastAPI vs. Microservices

### Options Considered
- **Monolithic FastAPI** (chosen) — Single application handling all endpoints
- Microservices with separate API gateway — One service per domain (ingestion, analytics, health)
- Serverless functions — AWS Lambda / Cloud Functions per endpoint

### Monolithic FastAPI (Chosen)

**Why:** For a 5-store retail analytics system processing ~10K events/hour, a monolithic architecture provides the best balance of simplicity, performance, and operational cost. FastAPI's async capabilities handle concurrent ingestion and analytics queries within a single process. SQLite in WAL mode provides sufficient concurrency without a separate database container.

**Architecture Within the Monolith:**
- **Ingestion Layer:** `POST /events/ingest` — batch validation, deduplication, UPSERT
- **Analytics Layer:** `/metrics`, `/funnel`, `/heatmap` — computed on-demand with cached aggregations
- **Health Layer:** `/health` — lightweight DB connectivity and lag checks
- **Error Layer:** Global exception handlers — 503 on DB failure, no stack trace leaks

**Trade-off Accepted:** As the system scales beyond ~50 stores or 100K events/hour, the monolith would need to be decomposed. The ingestion and analytics workloads have different resource profiles (CPU-bound vs. I/O-bound), and separating them would improve resource utilization at scale.

**Why Not Others:**
- **Microservices:** Would add network latency between services, require a service mesh, and complicate deployment. For 5 stores, the operational overhead outweighs any benefits.
- **Serverless:** Cold starts would violate the real-time SLA. SQLite doesn't work well with stateless functions. The always-on container model is more appropriate.

### Additional API Design Choices

**Idempotency:** Implemented via unique index on `event_id`. Duplicate events are silently ignored (UPSERT), ensuring exactly-once semantics even with retry logic in the detection pipeline.

**Graceful Degradation:** If SQLite becomes unavailable, all endpoints return HTTP 503 with `{"status": "degraded", "detail": "Database unavailable"}`. Raw stack traces are never exposed. The health endpoint continues to function via an in-memory cache of the last known state.

**Structured Logging:** Every request gets a `trace_id` (UUID v4) that flows through the entire request lifecycle. Log entries are JSON-formatted with fields for `trace_id`, `endpoint`, `method`, `status_code`, `duration_ms`, and `event_count` (for ingestion). This enables distributed tracing even in a monolith.

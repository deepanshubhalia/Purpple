# DESIGN.md — Apex Retail Store Intelligence System Architecture

## System Overview

The Apex Retail Store Intelligence System is a real-time analytics engine that transforms raw, anonymized CCTV video clips and POS transaction data into actionable retail intelligence. The system eliminates offline data blind spots by correlating visual foot traffic with transaction data.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA INGESTION LAYER                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  CCTV Clips  │  │   POS CSV    │  │  Simulator   │              │
│  │  (1080p/15fps)│  │ (timestamps)│  │  (dev mode)  │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                  │                       │
│         ▼                 ▼                  ▼                       │
│  ┌──────────────────────────────────────────────────────┐           │
│  │              detect.py (Vision Pipeline)              │           │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────────┐  │           │
│  │  │ YOLOv8  │─▶│ByteTrack│─▶│  OSNet  │─▶│ Zone   │  │           │
│  │  │ Detect  │  │  Track  │  │  Re-ID  │  │ Mapper │  │           │
│  │  └─────────┘  └─────────┘  └─────────┘  └───┬────┘  │           │
│  └──────────────────────────────────────────────┼───────┘           │
│                                                 │ JSONL              │
└─────────────────────────────────────────────────┼───────────────────┘
                                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        API LAYER (FastAPI)                          │
│  ┌────────────────────────────────────────────────────┐             │
│  │              POST /events/ingest                     │             │
│  │  • Batch up to 500 events                           │             │
│  │  • Idempotent (UPSERT on event_id)                  │             │
│  │  • Structured logging with trace_id                 │             │
│  │  • Async ingestion with background processing       │             │
│  └───────────────────┬────────────────────────────────┘             │
│                      │ SQLite (WAL mode)                            │
│                      ▼                                               │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │
│  │  /metrics  │  │  /funnel   │  │ /heatmap   │  │ /anomalies │    │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                           │
│  ┌─────────────────────────────────────────────────────┐            │
│  │              React Live Dashboard                    │            │
│  │  • Real-time KPI cards                               │            │
│  │  • Live event stream                                 │            │
│  │  • Funnel visualization                              │            │
│  │  • Heatmap grid                                      │            │
│  │  • Anomaly alerts                                    │            │
│  └─────────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Breakdown

### 1. Detection Pipeline (`detect.py`)
- **Input:** 1080p, 15fps video clips from 3 cameras per store (Entry, Main Floor, Billing)
- **Detection Model:** YOLOv8-nano for person detection (optimized for edge deployment)
- **Tracking:** ByteTrack for persistent tracking IDs across frames
- **Re-ID:** OSNet-x0.25 for cross-camera visitor matching
- **Zone Classification:** Homography-based mapping of pixel coordinates to store zones
- **Staff Filtering:** Uniform color histogram analysis + bounding box aspect ratio heuristics
- **Output:** JSONL event stream validated against the event schema

### 2. Intelligence API (FastAPI)
- **Database:** SQLite in WAL mode for concurrent read/write without locks
- **Event Model:** Normalized tables (events, visitors, stores, zones, anomalies)
- **Idempotency:** Unique index on `event_id` with UPSERT logic
- **Error Handling:** Custom exception handlers return 503 on DB failure, no stack trace leaks
- **Structured Logging:** JSON-formatted logs with `trace_id` correlation across requests

### 3. Analytics Engine
- **Conversion Rate:** Correlates POS timestamps with billing zone dwell windows
- **Funnel Analysis:** Entry → Zone Visit → Billing Queue → Purchase with drop-off tracking
- **Heatmap:** Normalized frequency grid with dwell-weighted intensity
- **Anomaly Detection:** Three anomaly types (BILLING_QUEUE_SPIKE, CONVERSION_DROP, DEAD_ZONE) with configurable thresholds

### 4. Event Simulator
- Generates realistic event streams for 5 stores with configurable parameters
- Simulates group entries, staff filtering, re-entries, camera overlap, and queue abandonment
- Outputs events in the exact JSONL schema expected by the ingest endpoint

## AI-Assisted Decisions

### Where LLM Shaped the Design

1. **Event Schema Structure:** An LLM suggested the flat event schema with `event_id`, `visitor_id`, `event_type`, `dwell_ms`, `is_staff`, `group_size`, `position`, and `confidence` fields. This eliminated the need for nested joins and simplified the ingestion pipeline. We adopted it with one modification: added `trace_id` for distributed tracing.

2. **Anomaly Threshold Design:** LLM recommended static thresholds for anomaly detection. We overrode this and implemented adaptive thresholds based on rolling 30-minute windows, as retail traffic patterns vary significantly by time of day.

3. **Database Choice:** LLM initially suggested PostgreSQL for production readiness. We chose SQLite with WAL mode for this project because: (a) single-container deployment, (b) SQLite handles 100K writes/sec in WAL mode, (c) eliminates the need for a separate container, (d) sufficient for the 5-store, demo-scale workload.

### Where We Overrode LLM Advice

1. **Detection Pipeline Architecture:** LLM suggested a microservices approach with separate containers for detection, tracking, and Re-ID. We kept it monolithic within `detect.py` to reduce operational complexity and because the pipeline processes clips sequentially, not in a streaming fashion.

2. **Staff Detection Method:** LLM recommended a full CNN-based uniform classifier. We simplified to color histogram + aspect ratio heuristics, which achieves 85%+ accuracy on controlled retail environments and runs 10x faster on CPU.

3. **API Pagination:** LLM recommended cursor-based pagination for all list endpoints. We implemented offset-based pagination since the dataset size (5 stores, ~10K events/hour) doesn't justify the complexity of cursor pagination.

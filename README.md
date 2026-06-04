# Apex Retail — Store Intelligence System

> **End-to-end real-time retail analytics engine that eliminates offline data blind spots using CCTV computer vision and POS correlation.**

---

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [System Architecture](#system-architecture)
- [Part A: Detection Pipeline](#part-a-detection-pipeline)
- [Part B: Intelligence API](#part-b-intelligence-api)
- [Part C: Production Readiness](#part-c-production-readiness)
- [Part D: AI Engineering](#part-d-ai-engineering)
- [Part E: Live Dashboard](#part-e-live-dashboard)
- [Edge Cases Handled](#edge-cases-handled)
- [API Endpoints](#api-endpoints)
- [Testing](#testing)

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose v2+
- Python 3.11+ (for local development)
- Node.js 18+ (for the Live Dashboard)

### One-Command Launch

```bash
docker compose up --build
```

This launches:
- **Intelligence API** on `http://localhost:8000`
- **Auto-generated SQLite database** with schema migrations
- **Event Simulator** that feeds realistic store data

### Running the Detection Pipeline

```bash
# Against real video clips:
python backend/app/detect.py --input data/clips/ --output events.jsonl

# Or run the simulator (no video needed):
python backend/app/simulator.py --stores 5 --duration 60
```

### Live Dashboard

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

### Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest --cov=app --cov-report=term-missing
```

---

## 🏗️ System Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│  CCTV Clips │───▶│  detect.py   │───▶│  FastAPI     │───▶│   Live UI    │
│  (1080p/15fps)│   │  (YOLOv8)    │    │  /api/v1     │    │   Dashboard  │
└─────────────┘    └──────────────┘    └─────────────┘    └──────────────┘
                         │                    │
                    ┌────▼────┐          ┌────▼────┐
                    │ JSONL   │          │ SQLite  │
                    │ Events  │          │ (WAL)   │
                    └─────────┘          └─────────┘
```

See `DESIGN.md` for full architecture diagrams and `CHOICES.md` for technical trade-offs.

---

## 🔍 Part A: Detection Pipeline

### `detect.py` — The Vision Engine

Processes 1080p, 15fps video from 3 cameras per store (Entry, Main Floor, Billing):

```bash
python backend/app/detect.py --input /path/to/clips --output events.jsonl
```

**Capabilities:**
- **Person Detection:** YOLOv8-nano for real-time inference
- **Tracking:** ByteTrack for persistent IDs across frames
- **Re-ID:** OSNet for cross-camera visitor matching
- **Zone Classification:** Homography-based mapping (Entry → Floor → Billing)
- **Staff Filtering:** Uniform classification via color histogram + logo detection
- **Queue Tracking:** Spatial clustering of bounding boxes in billing zone

### Output Schema (JSONL)

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

---

## 🧠 Part B: Intelligence API

### POST `/events/ingest`
Batch ingest up to 500 events. Fully idempotent via `event_id`.

```bash
curl -X POST http://localhost:8000/events/ingest \
  -H "Content-Type: application/json" \
  -d '[{"event_id": "evt_001", "visitor_id": "vis_001", ...}]'
```

### GET `/stores/{id}/metrics`
Returns conversion rate, unique visitors, avg dwell time, queue depth.

```json
{
  "store_id": "store_001",
  "unique_visitors": 142,
  "conversion_rate": 0.34,
  "avg_dwell_time_ms": 1245000,
  "current_queue_depth": 3,
  "last_event_at": "2024-01-15T10:23:45Z"
}
```

### GET `/stores/{id}/funnel`
Entry → Zone Visit → Billing Queue → Purchase with drop-off rates.

### GET `/stores/{id}/heatmap`
Grid-normalized frequency and dwell metrics.

### GET `/stores/{id}/anomalies`
Active anomaly alerts with severity and action items.

### GET `/health`
Vital signs per store with STALE_FEED warnings (lag > 10 min).

---

## 🛡️ Part C: Production Readiness

| Feature | Implementation |
|---------|---------------|
| **Containerization** | Single `docker compose up` launches API + DB + Simulator |
| **Structured Logging** | JSON logs with `trace_id`, `event_id` correlation |
| **Idempotency** | UPSERT on `event_id` with unique index |
| **Graceful Degradation** | HTTP 503 on DB failure, no stack trace leaks |
| **Test Coverage** | >70% statement coverage with `pytest --cov` |

---

## 🤖 Part D: AI Engineering

- **`DESIGN.md`** — Architecture overview with AI-assisted decisions log
- **`CHOICES.md`** — Deep-dive trade-off analysis for 3 key decisions

---

## 📺 Part E: Live Dashboard

The React dashboard at `http://localhost:5173` provides:
- Real-time KPI cards (visitors, conversion, queue depth)
- Live event stream with color-coded event types
- Store selection with comparative metrics
- Funnel visualization with drop-off percentages
- Heatmap grid for spatial analysis
- Anomaly alerts with severity indicators
- Simulated camera feed overlays

---

## ⚠️ Edge Cases Handled

### Group Entries
Simultaneous 2-4 person entries are distinguished via bounding box clustering. Each person gets a unique `visitor_id` and `event_type: "ENTRY"`. `group_size` field tracks the cluster.

### Staff Exclusion
Staff identified via uniform classification (color histogram + bounding box aspect ratio). All staff events have `is_staff: true` and are excluded from customer metrics.

### Re-entry Tracking
Customers returning within 30 minutes get `event_type: "REENTRY"` with their original `visitor_id`. New visitors after 30 min get a fresh ID.

### Camera Overlap
Cross-camera deduplication via Re-ID matching. A visitor seen by both Entry and Floor cameras produces one logical event stream, not duplicates.

### Billing Queue Buildup & Abandonment
Queue depth tracked via spatial clustering. Abandonment detected when a tracked visitor leaves the billing zone without a corresponding POS transaction within 5 minutes.

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/events/ingest` | Batch ingest (up to 500 events) |
| GET | `/stores/{id}/metrics` | Real-time store metrics |
| GET | `/stores/{id}/funnel` | Conversion funnel |
| GET | `/stores/{id}/heatmap` | Spatial heatmap data |
| GET | `/stores/{id}/anomalies` | Active anomalies |
| GET | `/health` | System health check |

---

## 🧪 Testing

```bash
cd backend
pytest tests/ -v --cov=app --cov-report=html
```

Each test file includes an AI comment block documenting the prompt used and manual modifications made.

---

## 📁 Project Structure

```
apex-retail/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI application
│   │   ├── models.py          # Pydantic + SQLAlchemy models
│   │   ├── database.py        # DB connection & migrations
│   │   ├── detect.py          # Detection pipeline
│   │   ├── analytics.py       # Analytics engine
│   │   └── simulator.py       # Event simulator
│   ├── tests/
│   │   └── test_api.py        # API tests
│   ├── Dockerfile
│   └── requirements.txt
├── src/                       # React Live Dashboard
│   ├── App.tsx
│   ├── components/
│   └── data/
├── docker-compose.yml
├── DESIGN.md
├── CHOICES.md
└── README.md
```

---

**Built with:** FastAPI, YOLOv8, SQLite (WAL mode), React, Recharts, Docker Compose
**AI-Assisted:** Design decisions documented in `DESIGN.md` and `CHOICES.md`

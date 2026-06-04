"""
SQLAlchemy ORM models and Pydantic schemas for Apex Retail Intelligence API.
"""

import uuid
from datetime import datetime
from typing import Optional, List
from enum import Enum

from sqlalchemy import (
    Column, String, Float, Boolean, Integer, DateTime,
    ForeignKey, Text, UniqueConstraint, Index
)
from sqlalchemy.orm import DeclarativeBase, relationship

from pydantic import BaseModel, Field


# ─── SQLAlchemy Models ──────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class Store(Base):
    __tablename__ = "stores"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    events = relationship("Event", back_populates="store")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_event_id"),
        Index("idx_store_timestamp", "store_id", "timestamp"),
        Index("idx_visitor_id", "visitor_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(36), unique=True, nullable=False, index=True)
    visitor_id = Column(String(36), nullable=False, index=True)
    store_id = Column(String(36), ForeignKey("stores.id"), nullable=False)
    camera_id = Column(String(50), nullable=False)
    event_type = Column(String(30), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    zone = Column(String(30), nullable=True)
    position_x = Column(Float, nullable=True)
    position_y = Column(Float, nullable=True)
    dwell_ms = Column(Integer, default=0)
    is_staff = Column(Boolean, default=False)
    group_size = Column(Integer, default=1)
    confidence = Column(Float, default=0.0)
    trace_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    store = relationship("Store", back_populates="events")


class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    anomaly_id = Column(String(36), unique=True, nullable=False)
    store_id = Column(String(36), ForeignKey("stores.id"), nullable=False)
    anomaly_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    description = Column(Text, nullable=False)
    action_items = Column(Text, nullable=False)
    detected_at = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)


class POSRecord(Base):
    __tablename__ = "pos_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String(36), unique=True, nullable=False)
    store_id = Column(String(36), ForeignKey("stores.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    amount = Column(Float, nullable=False)
    items_count = Column(Integer, default=1)
    visitor_id = Column(String(36), nullable=True)


# ─── Pydantic Schemas ───────────────────────────────────────────────────────

class Position(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class EventCreate(BaseModel):
    event_id: str
    visitor_id: str
    store_id: str
    camera_id: str
    event_type: str
    timestamp: datetime
    zone: Optional[str] = None
    position: Optional[Position] = None
    dwell_ms: int = 0
    is_staff: bool = False
    group_size: int = 1
    confidence: float = 1.0
    trace_id: Optional[str] = None


class EventResponse(BaseModel):
    event_id: str
    visitor_id: str
    store_id: str
    event_type: str
    timestamp: datetime
    is_staff: bool

    class Config:
        from_attributes = True


class IngestResponse(BaseModel):
    accepted: int
    duplicates: int
    rejected: int
    total: int


class MetricsResponse(BaseModel):
    store_id: str
    unique_visitors: int
    conversion_rate: float
    avg_dwell_time_ms: int
    current_queue_depth: int
    total_purchases: int
    last_event_at: Optional[str] = None


class FunnelStep(BaseModel):
    step: str
    count: int
    percentage: float
    drop_off: float


class FunnelResponse(BaseModel):
    store_id: str
    steps: List[FunnelStep]


class HeatmapCell(BaseModel):
    x: int
    y: int
    frequency: int
    avg_dwell_ms: int
    intensity: float


class HeatmapResponse(BaseModel):
    store_id: str
    grid_width: int = 10
    grid_height: int = 10
    cells: List[HeatmapCell]


class AnomalyResponse(BaseModel):
    anomaly_id: str
    store_id: str
    anomaly_type: str
    severity: str
    description: str
    action_items: str
    detected_at: datetime
    resolved: bool


class HealthResponse(BaseModel):
    status: str
    stores: dict
    database: str
    last_updated: datetime

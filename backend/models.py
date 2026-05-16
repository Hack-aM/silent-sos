"""
models.py — Database Models for Silent SOS System
===================================================
This file defines all database tables using SQLAlchemy ORM.
SQLAlchemy lets us write Python classes instead of raw SQL.

SCALABILITY NOTE: Designed for SQLite now, but 100% compatible
with PostgreSQL by changing DATABASE_URL in .env later.
"""

from datetime import datetime
from database.db import db  # Our shared SQLAlchemy instance


# ─────────────────────────────────────────────────────────
# USER MODEL
# Stores registered users of the Silent SOS platform.
# ─────────────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    # Full name of the user
    full_name = db.Column(db.String(150), nullable=False)

    # Email must be unique — no duplicate accounts
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)

    # Phone number for potential SMS alerts in future
    phone_number = db.Column(db.String(20), nullable=True)

    # SECURITY: We NEVER store plain passwords.
    # We store only the bcrypt hash. Even if the database is
    # stolen, the attacker cannot recover the original password.
    password_hash = db.Column(db.String(256), nullable=False)

    # Timestamp when the account was created
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships — one user has many contacts and alerts
    contacts = db.relationship("EmergencyContact", backref="user", lazy=True,
                               cascade="all, delete-orphan")
    alerts = db.relationship("Alert", backref="user", lazy=True,
                             cascade="all, delete-orphan")

    def to_dict(self):
        """Convert user object to JSON-safe dictionary (excludes password)."""
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "phone_number": self.phone_number,
            "created_at": self.created_at.isoformat()
        }

    def __repr__(self):
        return f"<User {self.email}>"


# ─────────────────────────────────────────────────────────
# EMERGENCY CONTACT MODEL
# Stores trusted people who receive SOS alerts.
# ─────────────────────────────────────────────────────────
class EmergencyContact(db.Model):
    __tablename__ = "emergency_contacts"

    id = db.Column(db.Integer, primary_key=True)

    # Foreign key — links this contact to a specific user
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    contact_name = db.Column(db.String(150), nullable=False)
    contact_phone = db.Column(db.String(20), nullable=False)

    # Relationship type: "Mother", "Friend", "Sister", etc.
    relation = db.Column(db.String(100), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        """Convert to JSON-safe dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "contact_name": self.contact_name,
            "contact_phone": self.contact_phone,
            "relation": self.relation,
            "created_at": self.created_at.isoformat()
        }

    def __repr__(self):
        return f"<Contact {self.contact_name} for User {self.user_id}>"


# ─────────────────────────────────────────────────────────
# ALERT MODEL
# Every SOS event creates one row here as evidence.
# ─────────────────────────────────────────────────────────
class Alert(db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)

    # Foreign key — which user triggered the alert
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # GPS coordinates captured at the moment of SOS
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    # Path to the uploaded audio recording (evidence)
    audio_filename = db.Column(db.String(300), nullable=True)

    # AI-computed danger score (0–100)
    # Higher score = higher detected danger level
    danger_score = db.Column(db.Float, nullable=True, default=0.0)

    # Risk level label: LOW, MEDIUM, HIGH
    risk_level = db.Column(db.String(20), nullable=True, default="UNKNOWN")

    # Dangerous keywords found in the audio transcript
    detected_keywords = db.Column(db.Text, nullable=True)

    # Current status of the alert
    # Values: "ACTIVE", "RESOLVED", "FALSE_ALARM"
    status = db.Column(db.String(20), nullable=False, default="ACTIVE")

    # Timestamp of when the alert was triggered
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        """Convert alert to JSON-safe dictionary for API responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "audio_filename": self.audio_filename,
            "danger_score": self.danger_score,
            "risk_level": self.risk_level,
            "detected_keywords": self.detected_keywords,
            "status": self.status,
            "created_at": self.created_at.isoformat()
        }

    def __repr__(self):
        return f"<Alert #{self.id} User={self.user_id} Score={self.danger_score}>"


# ─────────────────────────────────────────────────────────
# TRACKING SESSION MODEL
# Groups a continuous live tracking period into one session.
# A user can start/stop tracking multiple times per day.
# ─────────────────────────────────────────────────────────
class TrackingSession(db.Model):
    __tablename__ = "tracking_sessions"

    id = db.Column(db.Integer, primary_key=True)

    # Which user is being tracked
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Session lifecycle: ACTIVE while tracking, STOPPED when ended
    status = db.Column(db.String(20), nullable=False, default="ACTIVE")

    # Total number of GPS points received in this session
    total_points = db.Column(db.Integer, nullable=False, default=0)

    # Timestamps
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    stopped_at = db.Column(db.DateTime, nullable=True)

    # Relationship — one session has many tracking points
    points = db.relationship("TrackingPoint", backref="session", lazy=True,
                             cascade="all, delete-orphan",
                             order_by="TrackingPoint.recorded_at.asc()")

    def to_dict(self):
        """Convert tracking session to JSON-safe dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "status": self.status,
            "total_points": self.total_points,
            "started_at": self.started_at.isoformat(),
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None
        }

    def __repr__(self):
        return f"<TrackingSession #{self.id} User={self.user_id} Status={self.status}>"


# ─────────────────────────────────────────────────────────
# TRACKING POINT MODEL
# Each GPS coordinate captured during a live tracking session.
# Lightweight rows — designed for high-frequency inserts.
# ─────────────────────────────────────────────────────────
class TrackingPoint(db.Model):
    __tablename__ = "tracking_points"

    id = db.Column(db.Integer, primary_key=True)

    # Foreign key — which tracking session this point belongs to
    session_id = db.Column(db.Integer, db.ForeignKey("tracking_sessions.id"), nullable=False)

    # GPS coordinates
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    # Speed in m/s (from Geolocation API, can be null)
    speed = db.Column(db.Float, nullable=True)

    # When this point was recorded
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        """Convert tracking point to JSON-safe dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "lat": self.latitude,
            "lng": self.longitude,
            "speed": self.speed,
            "recorded_at": self.recorded_at.isoformat()
        }

    def __repr__(self):
        return f"<TrackingPoint Session={self.session_id} ({self.latitude}, {self.longitude})>"

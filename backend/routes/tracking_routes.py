"""
routes/tracking_routes.py — Live Tracking API Endpoints
========================================================
Handles real-time GPS tracking separately from emergency SOS alerts.

WHY SEPARATE FROM SOS:
  The SOS flow creates an Alert record in the database — that's for
  real emergencies. Live tracking sends GPS coordinates every 3–10s
  during a tracking session. If we reuse /send-sos for tracking,
  the alerts table fills with hundreds of non-emergency rows.

  This module stores tracking data in its own tables:
    - tracking_sessions: groups a period of continuous tracking
    - tracking_points:   individual GPS coordinates within a session

ENDPOINTS:
  POST /tracking/start     → Begin a new tracking session
  POST /tracking/update    → Add a GPS point to the active session
  POST /tracking/stop      → End the active tracking session
  GET  /tracking/active    → Get the current active session + points
  GET  /tracking/history   → Get past tracking sessions
"""

from datetime import datetime
from flask import Blueprint, request, jsonify, session, current_app

from database.db import db
from models import TrackingSession, TrackingPoint

tracking_bp = Blueprint("tracking", __name__)


def require_login():
    """Helper: check session auth and return user_id or error."""
    user_id = session.get("user_id")
    if not user_id:
        return None, (jsonify({"error": "Authentication required."}), 401)
    return user_id, None


# ─────────────────────────────────────────────────────────
# POST /tracking/start — Begin a New Tracking Session
# ─────────────────────────────────────────────────────────
@tracking_bp.route("/tracking/start", methods=["POST"])
def start_tracking():
    """
    Create a new tracking session for the logged-in user.
    Automatically closes any previously active session.

    Returns 201 with session_id for use in /tracking/update.
    """
    user_id, err = require_login()
    if err:
        return err

    # Auto-close any previously active tracking session
    active = TrackingSession.query.filter_by(
        user_id=user_id, status="ACTIVE"
    ).first()

    if active:
        active.status = "STOPPED"
        active.stopped_at = datetime.utcnow()
        current_app.logger.info(
            f"[TRACK] Auto-closed previous session #{active.id} for user {user_id}"
        )

    # Create new session
    new_session = TrackingSession(
        user_id=user_id,
        status="ACTIVE"
    )
    db.session.add(new_session)
    db.session.commit()

    current_app.logger.info(
        f"[TRACK] Session #{new_session.id} started for user {user_id}"
    )

    return jsonify({
        "message": "Tracking session started.",
        "session_id": new_session.id,
        "started_at": new_session.started_at.isoformat()
    }), 201


# ─────────────────────────────────────────────────────────
# POST /tracking/update — Add a GPS Point to Active Session
# ─────────────────────────────────────────────────────────
@tracking_bp.route("/tracking/update", methods=["POST"])
def update_tracking():
    """
    Record a GPS coordinate in the user's active tracking session.
    Designed for high-frequency calls (~every 3-10 seconds).

    Expected JSON:
    {
        "latitude": 28.6139,
        "longitude": 77.2090,
        "speed": 1.5,
        "session_id": 42
    }

    Returns 200 with point count.
    """
    user_id, err = require_login()
    if err:
        return err

    data = request.get_json() or {}
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    speed = data.get("speed")
    session_id = data.get("session_id")

    if latitude is None or longitude is None:
        return jsonify({"error": "Latitude and longitude are required."}), 400

    # Find the active session — either by provided ID or most recent
    if session_id:
        tracking = TrackingSession.query.filter_by(
            id=int(session_id), user_id=user_id, status="ACTIVE"
        ).first()
    else:
        tracking = TrackingSession.query.filter_by(
            user_id=user_id, status="ACTIVE"
        ).order_by(TrackingSession.started_at.desc()).first()

    if not tracking:
        return jsonify({"error": "No active tracking session found."}), 404

    # Create the tracking point
    point = TrackingPoint(
        session_id=tracking.id,
        latitude=float(latitude),
        longitude=float(longitude),
        speed=float(speed) if speed is not None else None
    )

    tracking.total_points += 1

    db.session.add(point)
    db.session.commit()

    return jsonify({
        "message": "Position recorded.",
        "session_id": tracking.id,
        "point_count": tracking.total_points
    }), 200


# ─────────────────────────────────────────────────────────
# POST /tracking/stop — End the Active Tracking Session
# ─────────────────────────────────────────────────────────
@tracking_bp.route("/tracking/stop", methods=["POST"])
def stop_tracking():
    """
    End the user's active tracking session.

    Returns 200 with session summary.
    """
    user_id, err = require_login()
    if err:
        return err

    tracking = TrackingSession.query.filter_by(
        user_id=user_id, status="ACTIVE"
    ).first()

    if not tracking:
        return jsonify({"message": "No active tracking session."}), 200

    tracking.status = "STOPPED"
    tracking.stopped_at = datetime.utcnow()
    db.session.commit()

    current_app.logger.info(
        f"[TRACK] Session #{tracking.id} stopped for user {user_id}. "
        f"Total points: {tracking.total_points}"
    )

    return jsonify({
        "message": "Tracking session stopped.",
        "session": tracking.to_dict()
    }), 200


# ─────────────────────────────────────────────────────────
# GET /tracking/active — Get Current Active Session + Points
# ─────────────────────────────────────────────────────────
@tracking_bp.route("/tracking/active", methods=["GET"])
def get_active_tracking():
    """
    Return the user's current active tracking session and its GPS points.
    Used by the frontend map to restore tracking state on page reload.
    """
    user_id, err = require_login()
    if err:
        return err

    tracking = TrackingSession.query.filter_by(
        user_id=user_id, status="ACTIVE"
    ).first()

    if not tracking:
        return jsonify({"active": False, "session": None, "points": []}), 200

    # Return the last 100 points to avoid huge payloads
    recent_points = TrackingPoint.query.filter_by(
        session_id=tracking.id
    ).order_by(TrackingPoint.recorded_at.desc()).limit(100).all()

    # Reverse so oldest is first (for polyline drawing)
    recent_points.reverse()

    return jsonify({
        "active": True,
        "session": tracking.to_dict(),
        "points": [p.to_dict() for p in recent_points]
    }), 200


# ─────────────────────────────────────────────────────────
# GET /tracking/history — Past Tracking Sessions
# ─────────────────────────────────────────────────────────
@tracking_bp.route("/tracking/history", methods=["GET"])
def get_tracking_history():
    """
    Return past tracking sessions for the logged-in user.
    """
    user_id, err = require_login()
    if err:
        return err

    sessions = TrackingSession.query.filter_by(user_id=user_id)\
                                     .order_by(TrackingSession.started_at.desc())\
                                     .limit(20)\
                                     .all()

    return jsonify({
        "sessions": [s.to_dict() for s in sessions],
        "total": len(sessions)
    }), 200

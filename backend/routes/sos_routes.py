"""
routes/sos_routes.py — SOS Alert API Endpoints
================================================
Handles all emergency functionality:
  - SOS alert creation with GPS
  - Audio evidence upload + AI analysis
  - Alert history
  - Alert GPS map data
  - Safe check-in
  - Unsafe area reporting
  - Fake call logging
"""

import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, session, current_app, send_from_directory

from database.db import db
from models import Alert, User, EmergencyContact
from utils.validators import is_allowed_audio_file, sanitize_filename
from ai.danger_analyzer import analyze_audio_file
from utils.sms_service import notify_emergency_contacts

sos_bp = Blueprint("sos", __name__)


def require_login():
    """
    Helper: Check if user is authenticated.
    Returns: (user_id, None) if logged in, (None, error_response) if not.
    """
    user_id = session.get("user_id")
    if not user_id:
        return None, (jsonify({"error": "Authentication required."}), 401)
    return user_id, None


# ─────────────────────────────────────────────────────────
# POST /send-sos — Create Emergency Alert Entry
# ─────────────────────────────────────────────────────────
@sos_bp.route("/send-sos", methods=["POST"])
def send_sos():
    """
    Create a new SOS alert. First call during emergency flow.

    Expected JSON:
    { "latitude": 28.6139, "longitude": 77.2090 }

    Returns 201 with alert_id for use in audio upload.
    """
    user_id, err = require_login()
    if err:
        return err

    data = request.get_json() or {}
    latitude  = data.get("latitude")
    longitude = data.get("longitude")

    alert = Alert(
        user_id=user_id,
        latitude=float(latitude) if latitude is not None else None,
        longitude=float(longitude) if longitude is not None else None,
        status="ACTIVE"
    )

    db.session.add(alert)
    db.session.commit()

    current_app.logger.info(
        f"[SOS] Alert #{alert.id} created for user {user_id} "
        f"at ({latitude}, {longitude})"
    )

    # Notify emergency contacts via SMS (graceful fallback)
    try:
        user = db.session.get(User, user_id)
        contacts = EmergencyContact.query.filter_by(user_id=user_id).all()
        sms_result = notify_emergency_contacts(
            user_name=user.full_name if user else "User",
            contacts=contacts,
            latitude=alert.latitude,
            longitude=alert.longitude,
            danger_score=0.0
        )
        current_app.logger.info(f"[SMS] Result: {sms_result}")
    except Exception as sms_err:
        current_app.logger.error(f"[SMS] Notification error: {sms_err}")

    return jsonify({
        "message": "SOS alert created. Stay safe!",
        "alert_id": alert.id,
        "status": alert.status,
        "created_at": alert.created_at.isoformat()
    }), 201


# ─────────────────────────────────────────────────────────
# POST /upload-audio — Upload Audio Evidence + AI Analysis
# ─────────────────────────────────────────────────────────
@sos_bp.route("/upload-audio", methods=["POST"])
def upload_audio():
    """
    Upload audio recording and run AI danger analysis.

    Expects multipart/form-data:
      - file: audio blob
      - alert_id: ID from /send-sos response
    """
    user_id, err = require_login()
    if err:
        return err

    if "file" not in request.files:
        return jsonify({"error": "No audio file provided."}), 400

    audio_file = request.files["file"]
    if not audio_file.filename:
        return jsonify({"error": "No filename provided."}), 400

    alert_id   = request.form.get("alert_id")

    if not alert_id:
        return jsonify({"error": "alert_id is required."}), 400

    alert = Alert.query.filter_by(id=int(alert_id), user_id=user_id).first()
    if not alert:
        return jsonify({"error": "Alert not found."}), 404

    original_name = audio_file.filename or "recording.webm"
    if not is_allowed_audio_file(original_name):
        return jsonify({"error": "Invalid file type. Only audio files accepted."}), 400

    ext       = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else "webm"
    safe_name = f"alert_{alert_id}_{uuid.uuid4().hex}.{ext}"
    safe_name = sanitize_filename(safe_name)

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    file_path  = os.path.join(upload_dir, safe_name)

    audio_file.save(file_path)

    # Validate saved file is not empty (MediaRecorder can produce 0-byte blobs)
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        os.remove(file_path)
        current_app.logger.warning(f"[UPLOAD] Empty audio file removed: {file_path}")
        return jsonify({"error": "Audio file is empty. Recording may have failed."}), 400

    current_app.logger.info(f"[UPLOAD] Audio saved: {file_path} ({file_size} bytes)")

    # Run AI danger analysis — wrapped in try/except so upload isn't lost on AI failure
    analysis = {"danger_score": 0.0, "detected_words": [], "risk_level": "UNKNOWN", "transcript": ""}
    try:
        analysis = analyze_audio_file(file_path)
    except Exception as ai_err:
        current_app.logger.error(f"[AI] Analysis crashed for alert #{alert_id}: {ai_err}")
        analysis["error"] = str(ai_err)

    alert.audio_filename    = safe_name
    alert.danger_score      = analysis.get("danger_score", 0.0)
    alert.risk_level        = analysis.get("risk_level", "UNKNOWN")
    alert.detected_keywords = ", ".join(analysis.get("detected_words", []))
    db.session.commit()

    current_app.logger.info(
        f"[AI] Alert #{alert_id}: Score={alert.danger_score}, Level={alert.risk_level}"
    )

    return jsonify({
        "message": "Audio analyzed successfully.",
        "alert_id": alert.id,
        "analysis": analysis
    }), 200


# ─────────────────────────────────────────────────────────
# GET /alerts — Fetch User's Alert History
# ─────────────────────────────────────────────────────────
@sos_bp.route("/alerts", methods=["GET"])
def get_alerts():
    """Return all past SOS alerts for the logged-in user, newest first."""
    user_id, err = require_login()
    if err:
        return err

    alerts = Alert.query.filter_by(user_id=user_id)\
                        .order_by(Alert.created_at.desc())\
                        .limit(20)\
                        .all()

    return jsonify({
        "alerts": [a.to_dict() for a in alerts],
        "total": len(alerts)
    }), 200


# ─────────────────────────────────────────────────────────
# GET /dashboard — Dashboard Summary Data
# ─────────────────────────────────────────────────────────
@sos_bp.route("/dashboard", methods=["GET"])
def get_dashboard():
    """Return user info, recent alerts, and safety statistics."""
    user_id, err = require_login()
    if err:
        return err

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    recent_alerts = Alert.query.filter_by(user_id=user_id)\
                               .order_by(Alert.created_at.desc())\
                               .limit(5)\
                               .all()

    total_alerts = Alert.query.filter_by(user_id=user_id).count()
    # Count both HIGH and CRITICAL risk events
    high_risk    = Alert.query.filter(
        Alert.user_id == user_id,
        Alert.risk_level.in_(["HIGH", "CRITICAL"])
    ).count()

    # Latest danger score
    latest = Alert.query.filter_by(user_id=user_id)\
                        .order_by(Alert.created_at.desc()).first()
    latest_score = latest.danger_score if latest else 0

    return jsonify({
        "user": user.to_dict(),
        "recent_alerts": [a.to_dict() for a in recent_alerts],
        "stats": {
            "total_alerts": total_alerts,
            "high_risk_events": high_risk,
            "latest_ai_score": latest_score
        }
    }), 200


# ─────────────────────────────────────────────────────────
# GET /alerts/map — GPS Points for Map View
# ─────────────────────────────────────────────────────────
@sos_bp.route("/alerts/map", methods=["GET"])
def get_alerts_map():
    """Return alert GPS points for Leaflet map markers."""
    user_id, err = require_login()
    if err:
        return err

    alerts = Alert.query.filter(
        Alert.user_id == user_id,
        Alert.latitude.isnot(None),
        Alert.longitude.isnot(None)
    ).order_by(Alert.created_at.desc()).limit(50).all()

    points = [{
        "lat": a.latitude,
        "lng": a.longitude,
        "risk_level": a.risk_level or "UNKNOWN",
        "danger_score": a.danger_score or 0,
        "created_at": a.created_at.isoformat(),
        "alert_id": a.id
    } for a in alerts]

    return jsonify({"points": points}), 200


# ─────────────────────────────────────────────────────────
# POST /safe-checkin — User confirms they are safe
# ─────────────────────────────────────────────────────────
@sos_bp.route("/safe-checkin", methods=["POST"])
def safe_checkin():
    """
    Record a safe check-in. Used by Safe Journey Mode
    to confirm the user arrived at their destination safely.
    """
    user_id, err = require_login()
    if err:
        return err

    data      = request.get_json() or {}
    timestamp = data.get("timestamp", datetime.utcnow().isoformat())

    current_app.logger.info(
        f"[CHECKIN] User {user_id} checked in safe at {timestamp}"
    )

    return jsonify({
        "message": "Safe check-in recorded.",
        "user_id": user_id,
        "timestamp": timestamp
    }), 200


# ─────────────────────────────────────────────────────────
# POST /report-unsafe — Report an unsafe area (heatmap)
# ─────────────────────────────────────────────────────────
@sos_bp.route("/report-unsafe", methods=["POST"])
def report_unsafe():
    """
    Allow users to anonymously report an unsafe location.
    Powers the community safety heatmap (future feature).

    Expected JSON:
    {
        "latitude": 28.6139,
        "longitude": 77.2090,
        "description": "Harassment reported near XYZ"
    }
    """
    user_id, err = require_login()
    if err:
        return err

    data        = request.get_json() or {}
    latitude    = data.get("latitude")
    longitude   = data.get("longitude")
    description = str(data.get("description", ""))[:500]

    current_app.logger.info(
        f"[REPORT] Unsafe area by user {user_id} "
        f"at ({latitude}, {longitude}): {description[:60]}"
    )

    # Future: INSERT into unsafe_reports table for heatmap
    return jsonify({
        "message": "Unsafe area report submitted. Thank you.",
        "location": {"lat": latitude, "lng": longitude}
    }), 201


# ─────────────────────────────────────────────────────────
# POST /fake-call — Log fake call usage (analytics)
# ─────────────────────────────────────────────────────────
@sos_bp.route("/fake-call", methods=["POST"])
def log_fake_call():
    """
    Log that the user activated the fake call escape feature.
    Analytics only — no personal data stored.
    """
    user_id, err = require_login()
    if err:
        return err

    current_app.logger.info(
        f"[FAKECALL] User {user_id} used fake call escape feature"
    )

    return jsonify({"message": "Fake call event logged."}), 200


# ─────────────────────────────────────────────────────────
# GET /audio/<filename> — Serve Audio Evidence for Playback
# ─────────────────────────────────────────────────────────
@sos_bp.route("/audio/<filename>", methods=["GET"])
def serve_audio(filename):
    """
    Serve an audio evidence file for playback in the Evidence Vault.
    Only serves files belonging to the authenticated user.
    """
    user_id, err = require_login()
    if err:
        return err

    # Security: sanitize filename to prevent path traversal
    safe_name = sanitize_filename(filename)
    if not safe_name:
        return jsonify({"error": "Invalid filename."}), 400

    # Verify this audio belongs to the requesting user
    alert = Alert.query.filter_by(
        user_id=user_id, audio_filename=safe_name
    ).first()

    if not alert:
        return jsonify({"error": "Audio file not found or access denied."}), 404

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(upload_dir, safe_name)

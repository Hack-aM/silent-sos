"""
utils/sms_service.py — SMS Alert Service via Twilio
=====================================================
When a user triggers SOS, this module sends real SMS messages
to all their saved emergency contacts.

SETUP INSTRUCTIONS:
  1. Create free Twilio account at https://twilio.com
  2. Get Account SID, Auth Token, and a Twilio phone number
  3. Add them to your .env file (see below)
  4. Install: python -m pip install twilio

COST: Twilio free trial gives ~$15 credit (enough for ~1000 SMS).

HOW IT WORKS:
  1. Fetch all emergency contacts for the user
  2. Build a detailed alert message with GPS link
  3. Send SMS to each contact via Twilio REST API
  4. Log success/failure for each
"""

import os
import logging

logger = logging.getLogger(__name__)

# ── Load Twilio credentials from environment ──────────────
# Never hardcode these — use .env file.
TWILIO_ACCOUNT_SID  = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER  = os.getenv("TWILIO_FROM_NUMBER", "")  # e.g. +14155552671

# Feature flag — SMS is disabled if credentials are not set
SMS_ENABLED = all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER])


def build_alert_message(user_name: str, latitude: float, longitude: float, danger_score: float) -> str:
    """
    Build the SMS message text sent to emergency contacts.

    Includes:
    - Who triggered the alert
    - Their GPS location as a Google Maps link
    - AI danger score
    - Timestamp
    """
    if latitude and longitude:
        maps_link = f"https://maps.google.com/?q={latitude},{longitude}"
        location_text = f"📍 Location: {maps_link}"
    else:
        location_text = "📍 Location: Not available"

    risk = "CRITICAL" if danger_score >= 70 else "HIGH" if danger_score >= 50 else "MEDIUM"

    message = (
        f"🚨 SILENT SOS ALERT 🚨\n"
        f"{user_name} has triggered an emergency SOS!\n\n"
        f"{location_text}\n"
        f"⚠️ Risk Level: {risk} (Score: {danger_score:.0f}/100)\n\n"
        f"Please contact them or call emergency services immediately.\n"
        f"— Silent SOS Safety System"
    )
    return message


def send_sms_to_contact(to_number: str, message: str) -> bool:
    """
    Send a single SMS to one phone number using Twilio.

    Args:
        to_number: Recipient's phone number (e.g. "+919876543210")
        message:   The SMS body text

    Returns:
        True if sent successfully, False otherwise
    """
    if not SMS_ENABLED:
        logger.warning("[SMS] Twilio credentials not configured. SMS skipped.")
        return False

    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        msg = client.messages.create(
            body=message,
            from_=TWILIO_FROM_NUMBER,
            to=to_number
        )

        logger.info(f"[SMS] Sent to {to_number} — SID: {msg.sid}")
        return True

    except ImportError:
        logger.warning("[SMS] twilio package not installed. Run: pip install twilio")
        return False
    except Exception as e:
        logger.error(f"[SMS] Failed to send to {to_number}: {e}")
        return False


def notify_emergency_contacts(user_name: str, contacts: list,
                               latitude: float, longitude: float,
                               danger_score: float) -> dict:
    """
    Send SOS SMS alerts to all emergency contacts.

    Args:
        user_name:    Full name of the user who triggered SOS
        contacts:     List of EmergencyContact ORM objects
        latitude:     GPS latitude (or None)
        longitude:    GPS longitude (or None)
        danger_score: AI-computed danger score (0–100)

    Returns:
        dict: { "sent": int, "failed": int, "skipped": bool }
    """
    if not SMS_ENABLED:
        logger.info("[SMS] SMS notifications disabled (no Twilio credentials).")
        return {"sent": 0, "failed": 0, "skipped": True}

    if not contacts:
        logger.info("[SMS] No emergency contacts to notify.")
        return {"sent": 0, "failed": 0, "skipped": False}

    message = build_alert_message(user_name, latitude, longitude, danger_score)

    sent_count   = 0
    failed_count = 0

    for contact in contacts:
        phone = contact.contact_phone.strip()
        if not phone:
            continue

        # Attempt to send SMS
        success = send_sms_to_contact(phone, message)
        if success:
            sent_count += 1
        else:
            failed_count += 1

    logger.info(
        f"[SMS] Notification complete: {sent_count} sent, {failed_count} failed "
        f"for user '{user_name}'"
    )

    return {"sent": sent_count, "failed": failed_count, "skipped": False}

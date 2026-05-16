"""
routes/contact_routes.py — Emergency Contact API Endpoints
===========================================================
Allows users to manage their emergency contacts:
  GET    /contacts         → List all contacts
  POST   /contacts         → Add a new contact
  PUT    /contacts/<id>    → Update a contact
  DELETE /contacts/<id>    → Delete a contact

WHY CONTACTS MATTER:
  When an SOS is triggered, the system should notify these trusted
  people. In this MVP we store them in the DB. Future integration
  with WhatsApp Business API or Twilio will send real SMS/messages.
"""

from flask import Blueprint, request, jsonify, session, current_app

from database.db import db
from models import EmergencyContact
from utils.validators import is_valid_phone, sanitize_text

contact_bp = Blueprint("contacts", __name__)


def require_login():
    """Helper: check session auth and return user_id or error."""
    user_id = session.get("user_id")
    if not user_id:
        return None, (jsonify({"error": "Authentication required."}), 401)
    return user_id, None


# ─────────────────────────────────────────────────────────
# GET /contacts — List All Contacts for Current User
# ─────────────────────────────────────────────────────────
@contact_bp.route("/contacts", methods=["GET"])
def get_contacts():
    """
    Return all emergency contacts for the logged-in user.
    """
    user_id, err = require_login()
    if err:
        return err

    contacts = EmergencyContact.query.filter_by(user_id=user_id)\
                                     .order_by(EmergencyContact.created_at.asc())\
                                     .all()
    return jsonify({
        "contacts": [c.to_dict() for c in contacts],
        "total": len(contacts)
    }), 200


# ─────────────────────────────────────────────────────────
# POST /contacts — Add a New Emergency Contact
# ─────────────────────────────────────────────────────────
@contact_bp.route("/contacts", methods=["POST"])
def add_contact():
    """
    Add a new emergency contact.

    Expected JSON body:
    {
        "contact_name": "Priya's Mom",
        "contact_phone": "+91 9876543210",
        "relation": "Mother"
    }

    Returns:
        201 Created with new contact data
        400 if validation fails
    """
    user_id, err = require_login()
    if err:
        return err

    data = request.get_json() or {}

    contact_name = sanitize_text(data.get("contact_name", ""), 150)
    contact_phone = data.get("contact_phone", "").strip()
    relation = sanitize_text(data.get("relation", ""), 100)

    # Validation
    if not contact_name or not contact_phone:
        return jsonify({"error": "Contact name and phone number are required."}), 400

    if not is_valid_phone(contact_phone):
        return jsonify({"error": "Invalid phone number format."}), 400

    # Limit to 10 contacts per user (prevent abuse)
    existing_count = EmergencyContact.query.filter_by(user_id=user_id).count()
    if existing_count >= 10:
        return jsonify({"error": "Maximum 10 emergency contacts allowed."}), 400

    contact = EmergencyContact(
        user_id=user_id,
        contact_name=contact_name,
        contact_phone=contact_phone,
        relation=relation if relation else "Contact"
    )

    db.session.add(contact)
    db.session.commit()

    current_app.logger.info(
        f"[CONTACTS] Contact added for user {user_id}: {contact_name}"
    )

    return jsonify({
        "message": "Emergency contact added.",
        "contact": contact.to_dict()
    }), 201


# ─────────────────────────────────────────────────────────
# PUT /contacts/<id> — Update an Emergency Contact
# ─────────────────────────────────────────────────────────
@contact_bp.route("/contacts/<int:contact_id>", methods=["PUT"])
def update_contact(contact_id):
    """
    Update an existing emergency contact.

    SECURITY: We verify the contact belongs to the current user
    before allowing any modification (IDOR protection).
    IDOR = Insecure Direct Object Reference attack.
    """
    user_id, err = require_login()
    if err:
        return err

    # IDOR protection: ensure this contact belongs to the current user
    contact = EmergencyContact.query.filter_by(
        id=contact_id, user_id=user_id
    ).first()

    if not contact:
        return jsonify({"error": "Contact not found."}), 404

    data = request.get_json() or {}

    # Only update fields that were provided
    if "contact_name" in data:
        contact.contact_name = sanitize_text(data["contact_name"], 150)

    if "contact_phone" in data:
        phone = data["contact_phone"].strip()
        if not is_valid_phone(phone):
            return jsonify({"error": "Invalid phone number format."}), 400
        contact.contact_phone = phone

    if "relation" in data:
        contact.relation = sanitize_text(data["relation"], 100)

    db.session.commit()

    return jsonify({
        "message": "Contact updated.",
        "contact": contact.to_dict()
    }), 200


# ─────────────────────────────────────────────────────────
# DELETE /contacts/<id> — Remove an Emergency Contact
# ─────────────────────────────────────────────────────────
@contact_bp.route("/contacts/<int:contact_id>", methods=["DELETE"])
def delete_contact(contact_id):
    """
    Delete an emergency contact.

    SECURITY: IDOR protection — user can only delete their own contacts.
    """
    user_id, err = require_login()
    if err:
        return err

    contact = EmergencyContact.query.filter_by(
        id=contact_id, user_id=user_id
    ).first()

    if not contact:
        return jsonify({"error": "Contact not found."}), 404

    contact_name = contact.contact_name
    db.session.delete(contact)
    db.session.commit()

    current_app.logger.info(
        f"[CONTACTS] Contact '{contact_name}' deleted for user {user_id}"
    )

    return jsonify({"message": f"Contact '{contact_name}' removed."}), 200

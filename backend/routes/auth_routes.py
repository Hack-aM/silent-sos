"""
routes/auth_routes.py — Authentication API Endpoints
=====================================================
Handles user registration, login, and logout.

SECURITY ARCHITECTURE:
- Passwords are NEVER stored in plain text.
- We use Werkzeug's generate_password_hash() which uses
  PBKDF2-HMAC-SHA256 with a random salt by default.
- Sessions are signed with Flask's SECRET_KEY, making them
  tamper-proof on the client side.

WHY FLASK SESSIONS:
- Server creates a signed cookie after login
- Every request with that cookie is automatically authenticated
- Cookie is cryptographically signed — cannot be forged without SECRET_KEY
"""

from flask import Blueprint, request, jsonify, session, current_app
from werkzeug.security import generate_password_hash, check_password_hash

from database.db import db
from models import User
from utils.validators import is_valid_email, is_valid_phone, is_strong_password, sanitize_text

# Blueprint groups related routes together
# This keeps auth routes separate from SOS routes, contacts routes, etc.
auth_bp = Blueprint("auth", __name__)


# ─────────────────────────────────────────────────────────
# POST /register — Create a New User Account
# ─────────────────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Register a new user.

    Expected JSON body:
    {
        "full_name": "Priya Sharma",
        "email": "priya@example.com",
        "phone_number": "+91 9876543210",
        "password": "SecurePass123"
    }

    Returns:
        201 Created with success message
        400 Bad Request if validation fails
        409 Conflict if email already exists
    """
    data = request.get_json()

    # VALIDATION 1: Check that required fields are present
    if not data:
        return jsonify({"error": "No data provided"}), 400

    full_name = sanitize_text(data.get("full_name", ""), 150)
    email = data.get("email", "").strip().lower()
    phone = data.get("phone_number", "").strip()
    password = data.get("password", "")

    if not full_name or not email or not password:
        return jsonify({"error": "Full name, email, and password are required."}), 400

    # VALIDATION 2: Check email format
    if not is_valid_email(email):
        return jsonify({"error": "Invalid email address format."}), 400

    # VALIDATION 3: Check phone number format (optional field)
    if phone and not is_valid_phone(phone):
        return jsonify({"error": "Invalid phone number format."}), 400

    # VALIDATION 4: Enforce strong password policy
    is_strong, pw_error = is_strong_password(password)
    if not is_strong:
        return jsonify({"error": pw_error}), 400

    # VALIDATION 5: Check for duplicate email
    # WHY: Two accounts with same email = confusion and security risk
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"error": "An account with this email already exists."}), 409

    # SECURITY: Hash the password before saving to database
    # generate_password_hash adds a random salt automatically
    hashed_password = generate_password_hash(password)

    # Create the new user record
    new_user = User(
        full_name=full_name,
        email=email,
        phone_number=phone if phone else None,
        password_hash=hashed_password
    )

    db.session.add(new_user)
    db.session.commit()

    current_app.logger.info(f"[AUTH] New user registered: {email}")

    return jsonify({
        "message": "Account created successfully! Please log in.",
        "user_id": new_user.id
    }), 201


# ─────────────────────────────────────────────────────────
# POST /login — Authenticate an Existing User
# ─────────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login an existing user and create a session.

    Expected JSON body:
    {
        "email": "priya@example.com",
        "password": "SecurePass123"
    }

    Returns:
        200 OK with user data
        400 Bad Request if fields missing
        401 Unauthorized if credentials wrong
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    # Find user by email
    user = User.query.filter_by(email=email).first()

    # SECURITY: Use check_password_hash to verify against stored hash.
    # WHY: We compare hash vs hash — never plaintext vs plaintext.
    # This protects against timing attacks too.
    if not user or not check_password_hash(user.password_hash, password):
        # SECURITY: Vague error message prevents email enumeration attacks.
        # (Attacker can't tell if email exists or password is wrong)
        return jsonify({"error": "Invalid email or password."}), 401

    # Create server-side session
    # Flask signs this cookie with SECRET_KEY — it cannot be forged
    session["user_id"] = user.id
    session["user_email"] = user.email
    session["user_name"] = user.full_name

    current_app.logger.info(f"[AUTH] User logged in: {email}")

    return jsonify({
        "message": "Login successful!",
        "user": user.to_dict()
    }), 200


# ─────────────────────────────────────────────────────────
# POST /logout — Clear User Session
# ─────────────────────────────────────────────────────────
@auth_bp.route("/logout", methods=["POST"])
def logout():
    """
    Log out the current user by clearing their session.

    Returns:
        200 OK always (even if not logged in)
    """
    user_email = session.get("user_email", "unknown")
    session.clear()  # Remove all session data
    current_app.logger.info(f"[AUTH] User logged out: {user_email}")
    return jsonify({"message": "Logged out successfully."}), 200


# ─────────────────────────────────────────────────────────
# GET /me — Get Current Logged-in User Info
# ─────────────────────────────────────────────────────────
@auth_bp.route("/me", methods=["GET"])
def get_current_user():
    """
    Return the currently authenticated user's data.
    Used by frontend to verify session on page load.

    Returns:
        200 with user data if logged in
        401 if not authenticated
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated."}), 401

    user = db.session.get(User, user_id)
    if not user:
        session.clear()
        return jsonify({"error": "User not found."}), 404

    return jsonify({"user": user.to_dict()}), 200

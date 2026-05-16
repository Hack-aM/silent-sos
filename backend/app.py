"""
app.py — Silent SOS System: Flask Application Entry Point
==========================================================
This is the main file that wires together all components:
  - Flask app configuration
  - Database initialization
  - Blueprint registration (routes)
  - CORS setup for frontend communication
  - Static file serving

APPLICATION FACTORY PATTERN:
  We use create_app() to build the Flask app.
  This makes testing easier and prevents circular imports.

HOW TO RUN:
  python app.py
  → Starts on http://localhost:5000

ARCHITECTURE OVERVIEW:
  app.py
    ├── routes/auth_routes.py     (login, register, logout)
    ├── routes/sos_routes.py      (SOS alerts, audio upload)
    ├── routes/contact_routes.py  (emergency contacts CRUD)
    ├── models.py                 (database schemas)
    ├── database/db.py            (SQLAlchemy instance)
    ├── ai/danger_analyzer.py     (AI analysis pipeline)
    └── utils/validators.py       (security helpers)
"""

import os
import sys
import logging
from flask import Flask, send_from_directory, send_file, session
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables from .env file
# WHY: Keeps secrets like SECRET_KEY out of source code
load_dotenv()

# ─────────────────────────────────────────────────────────
# CONFIGURE ROOT PATHS
# We need to tell Python where to find our modules since
# app.py is inside /backend but imports from /models, etc.
# ─────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")
TEMPLATES_DIR = os.path.join(FRONTEND_DIR, "templates")
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")
UPLOADS_DIR = os.path.join(BASE_DIR, "..", "uploads", "audio")

# Add backend directory to Python path
sys.path.insert(0, BASE_DIR)


def create_app():
    """
    Application Factory Function.
    Creates and configures the Flask application.
    
    WHY FACTORY PATTERN:
    - Allows creating multiple app instances (e.g., for testing)
    - Prevents circular import issues
    - Makes configuration flexible and injectable
    """

    # ── Initialize Flask ──────────────────────────────────
    app = Flask(
        __name__,
        template_folder=TEMPLATES_DIR,
        static_folder=STATIC_DIR
    )

    # ── App Configuration ─────────────────────────────────
    # SECRET_KEY: Signs session cookies and CSRF tokens.
    # NEVER hardcode this in production — use environment variable.
    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY",
        "fallback-dev-key-do-not-use-in-production"
    )

    # Database URI — uses SQLite for development
    # Change to postgresql://user:pass@host/db for production
    db_path = os.path.join(BASE_DIR, "silent_sos.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"

    # Disable modification tracking to save memory
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Max upload size: 16MB (prevents huge file uploads)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    # Upload folder path (for saving audio files)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = UPLOADS_DIR

    # Session cookie security settings
    app.config["SESSION_COOKIE_HTTPONLY"] = True   # JS cannot read cookie
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # Prevent CSRF
    # Set to True only when using HTTPS in production:
    # app.config["SESSION_COOKIE_SECURE"] = True

    # ── Setup Logging ─────────────────────────────────────
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    app.logger.setLevel(logging.INFO)

    # ── Initialize Database ───────────────────────────────
    from database.db import db
    db.init_app(app)

    # ── CORS Configuration ────────────────────────────────
    # FIX: Support same-origin requests + configurable production domains.
    # When frontend is served by Flask itself, CORS isn't strictly needed,
    # but we keep it for API flexibility (mobile apps, etc.)
    allowed_origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5000,http://127.0.0.1:5000"
    ).split(",")
    CORS(app, supports_credentials=True, origins=allowed_origins)

    # ── Register Route Blueprints ─────────────────────────
    from routes.auth_routes import auth_bp
    from routes.sos_routes import sos_bp
    from routes.contact_routes import contact_bp
    from routes.tracking_routes import tracking_bp

    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(sos_bp, url_prefix="/api")
    app.register_blueprint(contact_bp, url_prefix="/api")
    app.register_blueprint(tracking_bp, url_prefix="/api")

    # ── Create Database Tables ────────────────────────────
    with app.app_context():
        # Import models so SQLAlchemy knows about the tables
        import models  # noqa: F401
        db.create_all()
        app.logger.info("[DB] Database tables created/verified.")

    # ── Serve Frontend HTML Pages ─────────────────────────
    # Flask serves our frontend HTML templates directly.
    # In production, you'd use Nginx to serve static files.

    @app.route("/")
    def index():
        """Redirect to login page."""
        from flask import redirect
        return redirect("/login")

    @app.route("/login")
    def serve_login():
        """Serve the login page."""
        return send_file(os.path.join(TEMPLATES_DIR, "login.html"))

    @app.route("/signup")
    def serve_signup():
        """Serve the signup/registration page."""
        return send_file(os.path.join(TEMPLATES_DIR, "signup.html"))

    @app.route("/dashboard")
    def serve_dashboard():
        """
        Serve the dashboard page.
        FIX: Added server-side session check to prevent unauthorized
        access to the dashboard HTML. Unauthenticated users are
        redirected to login before any JS runs.
        """
        if not session.get("user_id"):
            from flask import redirect
            return redirect("/login")
        return send_file(os.path.join(TEMPLATES_DIR, "dashboard.html"))

    # ── Health Check Endpoint ─────────────────────────────
    @app.route("/health")
    def health():
        """Simple health check endpoint for monitoring."""
        return {"status": "ok", "system": "Silent SOS"}, 200

    app.logger.info("[APP] Silent SOS System initialized successfully.")
    return app


# ─────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = create_app()

    # debug=True: auto-reloads on code changes (development only!)
    # host="0.0.0.0": accessible from any network interface
    # In production, use Gunicorn: gunicorn -w 4 "app:create_app()"
    app.run(debug=True, host="0.0.0.0", port=5000)

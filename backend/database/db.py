"""
database/db.py — Shared SQLAlchemy Instance
=============================================
We create the db object here in its own file to avoid
circular imports between app.py and models.py.

Pattern used: Application Factory Pattern
- db is created separately
- then initialized with app inside create_app()
"""

from flask_sqlalchemy import SQLAlchemy

# This is our shared database object.
# It gets "attached" to the Flask app in app.py.
db = SQLAlchemy()

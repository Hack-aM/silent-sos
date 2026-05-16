"""
utils/validators.py — Input Validation & Security Utilities
=============================================================
SECURITY PRINCIPLE: Never trust user input.
All data entering the backend must be sanitized and validated
before touching the database or filesystem.

WHY THIS MATTERS:
- Prevents SQL injection (handled by SQLAlchemy ORM, but validation is extra protection)
- Prevents malicious file uploads (e.g., uploading .exe disguised as .wav)
- Prevents email spoofing and account abuse
"""

import re
import os

# ─────────────────────────────────────────────────────────
# ALLOWED AUDIO FILE EXTENSIONS
# We only accept standard audio formats.
# Rejecting unknown extensions prevents disguised malware uploads.
# ─────────────────────────────────────────────────────────
ALLOWED_AUDIO_EXTENSIONS = {"wav", "mp3", "ogg", "webm", "m4a", "flac"}


def is_valid_email(email: str) -> bool:
    """
    Validate email using a regex pattern.
    
    WHY: Prevents garbage data like 'abc' or 'x@' from entering the database.
    Also useful for preventing basic bot registrations.
    """
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email.strip()))


def is_valid_phone(phone: str) -> bool:
    """
    Validate phone number — allows digits, spaces, +, -, parentheses.
    
    Examples accepted: +91 9876543210, 9876543210, (123) 456-7890
    """
    if not phone:
        return True  # Phone is optional in our system
    pattern = r"^[\+\d\s\-\(\)]{7,20}$"
    return bool(re.match(pattern, phone.strip()))


def is_strong_password(password: str) -> tuple[bool, str]:
    """
    Check if a password meets minimum security requirements.
    
    Returns: (is_valid: bool, error_message: str)
    
    WHY: Weak passwords like '123456' or 'password' are the
    most common cause of account breaches.
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number."
    return True, "OK"


def is_allowed_audio_file(filename: str) -> bool:
    """
    Check if the uploaded file has an allowed audio extension.
    
    WHY: Without this check, an attacker could upload malicious
    scripts (like .php, .exe) to the uploads folder and execute them.
    
    HOW: We extract the extension and check against a whitelist.
    """
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_AUDIO_EXTENSIONS


def sanitize_filename(filename: str) -> str:
    """
    Remove dangerous characters from filenames.
    
    WHY: Filenames like '../../etc/passwd' could cause path traversal attacks,
    allowing access to files outside the uploads directory.
    
    HOW: We keep only safe characters (alphanumeric, dots, underscores, hyphens).
    """
    # Keep only safe characters
    safe_name = re.sub(r"[^\w\.\-]", "_", filename)
    # Prevent path traversal by removing directory separators
    safe_name = os.path.basename(safe_name)
    return safe_name


def sanitize_text(text: str, max_length: int = 150) -> str:
    """
    Strip dangerous HTML/script tags and limit string length.
    
    WHY: Prevents Cross-Site Scripting (XSS) where attackers inject
    JavaScript into stored data that runs in other users' browsers.
    """
    if not text:
        return ""
    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", "", text)
    # Trim whitespace
    clean = clean.strip()
    # Enforce maximum length
    return clean[:max_length]

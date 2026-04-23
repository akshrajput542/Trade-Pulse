"""
Authentication helper — handles user registration, login, and session management.
Uses SHA-256 hashing (for simplicity without external deps).
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict

from sqlalchemy.orm import Session
from database.models import User, AutoTradeConfig


def _hash_password(password: str, salt: str = None) -> str:
    """Hash password with SHA-256 + salt."""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}${hashed}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash."""
    salt = stored_hash.split("$")[0]
    return _hash_password(password, salt) == stored_hash


def register_user(session: Session, username: str, email: str,
                  password: str, full_name: str = None) -> Dict:
    """Register a new user. Returns dict with success status."""
    # Check existing
    if session.query(User).filter_by(username=username).first():
        return {"success": False, "error": "Username already taken"}
    if session.query(User).filter_by(email=email).first():
        return {"success": False, "error": "Email already registered"}

    if len(password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters"}

    user = User(
        username=username,
        email=email,
        password_hash=_hash_password(password),
        full_name=full_name or username,
    )
    session.add(user)
    session.commit()

    return {"success": True, "user_id": user.id, "username": user.username}


def login_user(session: Session, username: str, password: str) -> Dict:
    """Authenticate a user. Returns dict with user info + session_token on success."""
    user = session.query(User).filter_by(username=username).first()
    if not user:
        return {"success": False, "error": "Invalid username or password"}

    if not _verify_password(password, user.password_hash):
        return {"success": False, "error": "Invalid username or password"}

    # Generate persistent session token (survives browser refresh)
    token = secrets.token_hex(64)
    user.session_token = token
    user.session_expiry = datetime.utcnow() + timedelta(days=7)
    user.last_login = datetime.utcnow()
    session.commit()

    return {
        "success": True,
        "user_id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "session_token": token,
    }


def validate_session_token(session: Session, token: str) -> Optional[Dict]:
    """Validate a session token and return user info if valid.
    Returns None if token is invalid or expired.
    """
    if not token:
        return None
    user = session.query(User).filter_by(session_token=token).first()
    if not user:
        return None
    # Check expiry
    if user.session_expiry and user.session_expiry < datetime.utcnow():
        # Token expired — clear it
        user.session_token = None
        user.session_expiry = None
        session.commit()
        return None
    return {
        "success": True,
        "user_id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "session_token": token,
    }


def logout_user(session: Session, token: str):
    """Invalidate a session token (sign out)."""
    if not token:
        return
    user = session.query(User).filter_by(session_token=token).first()
    if user:
        user.session_token = None
        user.session_expiry = None
        session.commit()


def get_user_profile(session: Session, user_id: int) -> Optional[Dict]:
    """Get user profile by ID."""
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        return None
    return {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "created_at": user.created_at,
        "last_login": user.last_login,
    }

"""
User model with SQLite storage for magic-link authentication
"""

import os
import sqlite3
import uuid
import secrets
import time
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager

from ..utils.logger import get_logger

logger = get_logger('agenikpredict.user')

DB_PATH = os.path.join(os.path.dirname(__file__), '../../data/users.db')


def _ensure_db_dir():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


@contextmanager
def get_db():
    """Thread-safe SQLite connection context manager"""
    _ensure_db_dir()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize user tables"""
    _ensure_db_dir()
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT DEFAULT '',
                role TEXT DEFAULT 'user' CHECK(role IN ('user', 'admin', 'demo')),
                plan TEXT DEFAULT 'explorer' CHECK(plan IN ('explorer', 'starter', 'pro', 'enterprise')),
                created_at TEXT NOT NULL,
                last_login_at TEXT,
                is_active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS magic_links (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at REAL NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            CREATE INDEX IF NOT EXISTS idx_magic_links_token ON magic_links(token);
            CREATE INDEX IF NOT EXISTS idx_magic_links_expires ON magic_links(expires_at);
        """)

    logger.info("User database initialized")


def seed_admin(email=None, name="Alex", plan="pro"):
    """Seed the admin account if it doesn't exist"""
    if email is None:
        email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()

        if existing:
            logger.info(f"Admin account already exists: {email}")
            return existing['id']

        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        conn.execute(
            "INSERT INTO users (id, email, name, role, plan, created_at) "
            "VALUES (?, ?, ?, 'admin', ?, ?)",
            (user_id, email, name, plan, now_iso)
        )
        logger.info(f"Admin account created: {email} (id={user_id})")
        return user_id


def seed_demo(email="demo@agenikpredict.com", name="Demo User"):
    """Seed a demo account"""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()

        if existing:
            return existing['id']

        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        conn.execute(
            "INSERT INTO users (id, email, name, role, plan, created_at) "
            "VALUES (?, ?, ?, 'demo', 'explorer', ?)",
            (user_id, email, name, now_iso)
        )
        logger.info(f"Demo account created: {email}")
        return user_id


# ── User CRUD ──

def get_user_by_email(email):
    """Find user by email, returns dict or None"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1", (email.lower().strip(),)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id):
    """Find user by ID, returns dict or None"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def create_user(email, name="", plan="explorer"):
    """Create a new user"""
    email = email.lower().strip()
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (id, email, name, role, plan, created_at) "
            "VALUES (?, ?, ?, 'user', ?, ?)",
            (user_id, email, name, plan, now_iso)
        )
    logger.info(f"User created: {email} (id={user_id})")
    return get_user_by_id(user_id)


def update_last_login(user_id):
    """Update user's last login timestamp"""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?", (now, user_id)
        )


# ── Magic Link ──

def create_magic_link(user_id, ttl_seconds=600):
    """
    Create a magic link token (valid for 10 minutes by default).
    Returns the token string.
    """
    token = secrets.token_urlsafe(48)
    link_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    expires_at = time.time() + ttl_seconds

    with get_db() as conn:
        # Clean up old expired tokens for this user
        conn.execute(
            "DELETE FROM magic_links WHERE user_id = ? AND (expires_at < ? OR used = 1)",
            (user_id, time.time())
        )
        conn.execute(
            "INSERT INTO magic_links (id, user_id, token, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (link_id, user_id, token, expires_at, now)
        )
    return token


def verify_magic_link(token):
    """
    Verify and consume a magic link token.
    Returns user dict if valid, None if invalid/expired/used.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM magic_links WHERE token = ? AND used = 0 AND expires_at > ?",
            (token, time.time())
        ).fetchone()

        if not row:
            return None

        # Mark as used
        conn.execute(
            "UPDATE magic_links SET used = 1 WHERE id = ?", (row['id'],)
        )

    # Update login time and return user
    update_last_login(row['user_id'])
    return get_user_by_id(row['user_id'])


def cleanup_expired_links():
    """Remove all expired magic links"""
    with get_db() as conn:
        conn.execute(
            "DELETE FROM magic_links WHERE expires_at < ? OR used = 1",
            (time.time(),)
        )


def get_user_billing_status(user_id):
    """
    Get billing status for a user.
    Open-source version: generation is always allowed.
    """
    user = get_user_by_id(user_id)
    if not user:
        return {'can_generate': False}

    return {'can_generate': True}

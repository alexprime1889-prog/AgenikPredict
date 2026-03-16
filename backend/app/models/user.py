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
                is_active INTEGER DEFAULT 1,
                trial_ends_at TEXT,
                balance_cents INTEGER DEFAULT 0
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

            CREATE TABLE IF NOT EXISTS usage_log (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                estimated_cost_cents INTEGER DEFAULT 0,
                report_id TEXT,
                simulation_id TEXT,
                model TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            CREATE INDEX IF NOT EXISTS idx_magic_links_token ON magic_links(token);
            CREATE INDEX IF NOT EXISTS idx_magic_links_expires ON magic_links(expires_at);
            CREATE INDEX IF NOT EXISTS idx_usage_log_user ON usage_log(user_id);
            CREATE INDEX IF NOT EXISTS idx_usage_log_created ON usage_log(created_at);
        """)

        # Migrate existing databases: add new columns if missing
        _migrate_add_column(conn, 'users', 'trial_ends_at', 'TEXT')
        _migrate_add_column(conn, 'users', 'balance_cents', 'INTEGER DEFAULT 0')

    logger.info("User database initialized")


def _migrate_add_column(conn, table, column, col_type):
    """Safely add a column to an existing table (no-op if already exists)"""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        logger.info(f"Migration: added {column} to {table}")
    except sqlite3.OperationalError:
        # Column already exists
        pass


def seed_admin(email="alex@manogrand.ai", name="Alex", plan="pro"):
    """Seed the admin account if it doesn't exist"""
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
        # Admins get no trial restriction (can_generate is always true for admins)
        trial_ends_at = now_iso
        conn.execute(
            "INSERT INTO users (id, email, name, role, plan, created_at, trial_ends_at, balance_cents) "
            "VALUES (?, ?, ?, 'admin', ?, ?, ?, 0)",
            (user_id, email, name, plan, now_iso, trial_ends_at)
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
        trial_ends_at = (now + timedelta(days=2)).isoformat()
        conn.execute(
            "INSERT INTO users (id, email, name, role, plan, created_at, trial_ends_at, balance_cents) "
            "VALUES (?, ?, ?, 'demo', 'explorer', ?, ?, 0)",
            (user_id, email, name, now_iso, trial_ends_at)
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
    """Create a new user with a 2-day trial period"""
    email = email.lower().strip()
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    trial_ends_at = (now + timedelta(days=2)).isoformat()

    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (id, email, name, role, plan, created_at, trial_ends_at, balance_cents) "
            "VALUES (?, ?, ?, 'user', ?, ?, ?, 0)",
            (user_id, email, name, plan, now_iso, trial_ends_at)
        )
    logger.info(f"User created: {email} (id={user_id}, trial_ends_at={trial_ends_at})")
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


# ── Trial & Billing ──

def is_in_trial(user_id):
    """Check if the user is currently in their trial period"""
    user = get_user_by_id(user_id)
    if not user or not user.get('trial_ends_at'):
        return False
    try:
        trial_end = datetime.fromisoformat(user['trial_ends_at'])
        if trial_end.tzinfo is None:
            trial_end = trial_end.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < trial_end
    except (ValueError, TypeError):
        return False


def get_user_billing_status(user_id):
    """
    Get comprehensive billing status for a user.
    Returns dict with trial info, balance, and generation eligibility.
    """
    user = get_user_by_id(user_id)
    if not user:
        return {
            'is_trial': False,
            'trial_ends_at': None,
            'trial_days_left': 0,
            'balance_cents': 0,
            'can_generate': False,
        }

    trial_ends_at = user.get('trial_ends_at')
    balance_cents = user.get('balance_cents') or 0
    in_trial = False
    trial_days_left = 0

    if trial_ends_at:
        try:
            trial_end = datetime.fromisoformat(trial_ends_at)
            if trial_end.tzinfo is None:
                trial_end = trial_end.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if now < trial_end:
                in_trial = True
                delta = trial_end - now
                trial_days_left = max(0, delta.days + (1 if delta.seconds > 0 else 0))
        except (ValueError, TypeError):
            pass

    # Admins can always generate
    is_admin = user.get('role') == 'admin'
    can_generate = is_admin or in_trial or balance_cents > 0

    return {
        'is_trial': in_trial,
        'trial_ends_at': trial_ends_at,
        'trial_days_left': trial_days_left,
        'balance_cents': balance_cents,
        'can_generate': can_generate,
    }


# ── Balance Management ──

def get_balance(user_id):
    """Get current balance in cents"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT balance_cents FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return row['balance_cents'] if row else 0


def add_credits(user_id, amount_cents):
    """Add credits to user balance (after Stripe payment)"""
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET balance_cents = balance_cents + ? WHERE id = ?",
            (amount_cents, user_id)
        )
    logger.info(f"Credits added: user={user_id}, amount_cents={amount_cents}")


def deduct_credits(user_id, amount_cents):
    """Deduct credits after report generation"""
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET balance_cents = MAX(0, balance_cents - ?) WHERE id = ?",
            (amount_cents, user_id)
        )
    logger.info(f"Credits deducted: user={user_id}, amount_cents={amount_cents}")


# ── Usage Logging ──

def log_usage(user_id, action_type, input_tokens, output_tokens, model,
              report_id=None, simulation_id=None):
    """
    Log token usage for billing.
    Cost model: Claude Sonnet input=$3/1M, output=$15/1M, + 20% markup.
    """
    total_tokens = input_tokens + output_tokens
    input_cost = (input_tokens / 1_000_000) * 3.00 * 1.20
    output_cost = (output_tokens / 1_000_000) * 15.00 * 1.20
    total_cost_cents = int((input_cost + output_cost) * 100)

    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        conn.execute(
            "INSERT INTO usage_log "
            "(id, user_id, action_type, input_tokens, output_tokens, total_tokens, "
            "estimated_cost_cents, report_id, simulation_id, model, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (entry_id, user_id, action_type, input_tokens, output_tokens,
             total_tokens, total_cost_cents, report_id, simulation_id, model, now)
        )
    logger.info(
        f"Usage logged: user={user_id}, action={action_type}, "
        f"tokens={total_tokens}, cost_cents={total_cost_cents}"
    )
    return total_cost_cents


def get_user_usage(user_id, days=30):
    """Get usage history for a user within the last N days"""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM usage_log WHERE user_id = ? AND created_at > ? "
            "ORDER BY created_at DESC",
            (user_id, cutoff)
        ).fetchall()
        return [dict(r) for r in rows]


def get_user_total_cost(user_id):
    """Get total cost in cents for a user (all time)"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(estimated_cost_cents), 0) as total "
            "FROM usage_log WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        return row['total'] if row else 0

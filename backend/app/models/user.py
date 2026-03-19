"""
User model — PostgreSQL in production, SQLite fallback for local dev.
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

DATABASE_URL = os.environ.get('DATABASE_URL')
PH = '%s' if DATABASE_URL else '?'   # SQL placeholder


# ── Postgres wrapper (makes psycopg2 behave like sqlite3) ────────────────────

class _PgConn:
    """Thin wrapper so psycopg2 connection exposes .execute() like sqlite3."""

    def __init__(self, conn):
        import psycopg2.extras
        self._conn = conn
        self._extras = psycopg2.extras

    def execute(self, sql, params=()):
        cur = self._conn.cursor(cursor_factory=self._extras.RealDictCursor)
        cur.execute(sql, params)
        return cur

    def executemany(self, sql, params_list):
        cur = self._conn.cursor()
        cur.executemany(sql, params_list)
        return cur

    def commit(self):   self._conn.commit()
    def rollback(self): self._conn.rollback()
    def close(self):    self._conn.close()


# ── connection context manager ───────────────────────────────────────────────

@contextmanager
def get_db():
    if DATABASE_URL:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        pg = _PgConn(conn)
        try:
            yield pg
            pg.commit()
        except Exception:
            pg.rollback()
            raise
        finally:
            pg.close()
    else:
        db_path = os.path.join(os.path.dirname(__file__), '../../data/users.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA foreign_keys=ON')
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


# ── schema ────────────────────────────────────────────────────────────────────

def init_db():
    """Create all tables if they don't exist. Safe to call on every startup."""
    with get_db() as conn:
        stmts = [
            """CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT DEFAULT '',
                role TEXT DEFAULT 'user',
                plan TEXT DEFAULT 'explorer',
                balance_cents INTEGER DEFAULT 0,
                trial_ends_at TEXT,
                created_at TEXT NOT NULL,
                last_login_at TEXT,
                is_active INTEGER DEFAULT 1
            )""",
            """CREATE TABLE IF NOT EXISTS magic_links (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at REAL NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS usage_log (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                action_type TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                estimated_cost_cents INTEGER DEFAULT 0,
                report_id TEXT,
                simulation_id TEXT,
                model TEXT,
                created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS stripe_webhook_events (
                id TEXT PRIMARY KEY,
                stripe_event_id TEXT UNIQUE NOT NULL,
                event_type TEXT NOT NULL,
                user_id TEXT,
                amount_cents INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
            "CREATE INDEX IF NOT EXISTS idx_magic_links_token ON magic_links(token)",
            "CREATE INDEX IF NOT EXISTS idx_magic_links_expires ON magic_links(expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_usage_log_user ON usage_log(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_usage_log_created ON usage_log(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_stripe_events_event_id ON stripe_webhook_events(stripe_event_id)",
        ]
        for stmt in stmts:
            conn.execute(stmt)

    # Migration: add columns to existing DBs
    try:
        with get_db() as conn:
            conn.execute("ALTER TABLE users ADD COLUMN balance_cents INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        with get_db() as conn:
            conn.execute("ALTER TABLE users ADD COLUMN trial_ends_at TEXT")
    except Exception:
        pass

    logger.info("Database initialized")


# ── seed accounts ─────────────────────────────────────────────────────────────

def seed_admin(email=None, name="Alex", plan="pro"):
    if email is None:
        email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
    with get_db() as conn:
        existing = conn.execute(
            f"SELECT id FROM users WHERE email = {PH}", (email,)
        ).fetchone()
        if existing:
            return existing['id']
        user_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        conn.execute(
            f"INSERT INTO users (id, email, name, role, plan, balance_cents, created_at) "
            f"VALUES ({PH},{PH},{PH},'admin',{PH},0,{PH})",
            (user_id, email, name, plan, now_iso)
        )
        logger.info(f"Admin created: {email}")
        return user_id


def seed_demo():
    email = 'demo@agenikpredict.com'
    with get_db() as conn:
        existing = conn.execute(
            f"SELECT id FROM users WHERE email = {PH}", (email,)
        ).fetchone()
        if existing:
            return existing['id']
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        trial_ends = (now + timedelta(days=7)).isoformat()
        conn.execute(
            f"INSERT INTO users (id, email, name, role, plan, balance_cents, trial_ends_at, created_at) "
            f"VALUES ({PH},{PH},'Demo User','demo','explorer',0,{PH},{PH})",
            (user_id, email, trial_ends, now.isoformat())
        )
        return user_id


# ── user CRUD ─────────────────────────────────────────────────────────────────

def get_user_by_email(email):
    with get_db() as conn:
        row = conn.execute(
            f"SELECT * FROM users WHERE email = {PH}", (email,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id):
    with get_db() as conn:
        row = conn.execute(
            f"SELECT * FROM users WHERE id = {PH}", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def create_user(email, name='', role='user', plan='explorer'):
    with get_db() as conn:
        existing = conn.execute(
            f"SELECT id FROM users WHERE email = {PH}", (email,)
        ).fetchone()
        if existing:
            return existing['id']
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        trial_ends = (now + timedelta(days=14)).isoformat()
        conn.execute(
            f"INSERT INTO users (id, email, name, role, plan, balance_cents, trial_ends_at, created_at) "
            f"VALUES ({PH},{PH},{PH},{PH},{PH},0,{PH},{PH})",
            (user_id, email, name, role, plan, trial_ends, now.isoformat())
        )
        return user_id


def update_last_login(user_id):
    with get_db() as conn:
        conn.execute(
            f"UPDATE users SET last_login_at = {PH} WHERE id = {PH}",
            (datetime.now(timezone.utc).isoformat(), user_id)
        )


def get_all_users():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


# ── magic links ───────────────────────────────────────────────────────────────

def create_magic_link(user_id):
    token = secrets.token_urlsafe(32)
    link_id = str(uuid.uuid4())
    expires_at = time.time() + 3600  # 1 hour
    with get_db() as conn:
        conn.execute(
            f"INSERT INTO magic_links (id, user_id, token, expires_at, created_at) "
            f"VALUES ({PH},{PH},{PH},{PH},{PH})",
            (link_id, user_id, token, expires_at, datetime.now(timezone.utc).isoformat())
        )
    return token


def verify_magic_link(token):
    with get_db() as conn:
        row = conn.execute(
            f"SELECT * FROM magic_links WHERE token = {PH} AND used = 0 AND expires_at > {PH}",
            (token, time.time())
        ).fetchone()
        if not row:
            return None
        conn.execute(
            f"UPDATE magic_links SET used = 1 WHERE id = {PH}", (row['id'],)
        )
        return row['user_id']


def cleanup_expired_links():
    with get_db() as conn:
        conn.execute(
            f"DELETE FROM magic_links WHERE expires_at < {PH} OR used = 1",
            (time.time(),)
        )


# ── billing ───────────────────────────────────────────────────────────────────

REPORT_PRICE_CENTS = 500  # $5


def _get_trial_status(user):
    """Return active-trial state for a user record."""
    trial_ends_at = user.get('trial_ends_at')
    in_trial = False
    trial_days_left = 0

    if trial_ends_at and user.get('role') not in ('admin', 'demo'):
        try:
            trial_end = datetime.fromisoformat(trial_ends_at)
            if trial_end.tzinfo is None:
                trial_end = trial_end.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if trial_end > now:
                in_trial = True
                trial_days_left = max((trial_end - now).days, 0)
        except Exception:
            logger.warning("Failed to parse trial_ends_at for user %s", user.get('id'))

    return in_trial, trial_ends_at, trial_days_left


def _estimate_usage_cost_cents(input_tokens, output_tokens):
    """Estimate model cost with the same markup used in usage logging."""
    return int(((input_tokens / 1_000_000) * 3 + (output_tokens / 1_000_000) * 15) * 100 * 1.2)


def _get_report_slot_count(conn, user_id):
    """
    Count report slots already consumed or reserved for the user.

    Pending rows are included so concurrent requests cannot consume the same
    "free" slot or overspend the same balance before billing is finalized.
    """
    row = conn.execute(
        f"SELECT COUNT(*) as cnt FROM usage_log "
        f"WHERE user_id = {PH} AND action_type IN ('report_generate', 'report_generate_pending')",
        (user_id,)
    ).fetchone()
    return row['cnt'] if row else 0


def _get_report_cost_for_slot_count(user, slot_count):
    if user.get('role') in ('admin', 'demo'):
        return 0

    in_trial, _, _ = _get_trial_status(user)
    if in_trial:
        return 0

    if slot_count == 0:
        return 0   # first report free
    if (slot_count + 1) % 10 == 0:
        return 0   # every 10th free
    return REPORT_PRICE_CENTS


def get_balance(user_id):
    with get_db() as conn:
        row = conn.execute(
            f"SELECT balance_cents FROM users WHERE id = {PH}", (user_id,)
        ).fetchone()
        return row['balance_cents'] if row else 0


def add_credits(user_id, amount_cents):
    with get_db() as conn:
        conn.execute(
            f"UPDATE users SET balance_cents = balance_cents + {PH} WHERE id = {PH}",
            (amount_cents, user_id)
        )


def apply_stripe_credit_event(stripe_event_id, event_type, user_id, amount_cents):
    """
    Atomically record a Stripe event and credit the user balance once.

    Returns True when credits were applied, False when the event was already
    processed.
    """
    with get_db() as conn:
        try:
            conn.execute(
                f"INSERT INTO stripe_webhook_events "
                f"(id, stripe_event_id, event_type, user_id, amount_cents, created_at) "
                f"VALUES ({PH},{PH},{PH},{PH},{PH},{PH})",
                (
                    str(uuid.uuid4()),
                    stripe_event_id,
                    event_type,
                    user_id,
                    amount_cents,
                    datetime.now(timezone.utc).isoformat(),
                )
            )
        except Exception as exc:
            message = str(exc).lower()
            if 'unique' in message or 'duplicate key' in message:
                return False
            raise

        conn.execute(
            f"UPDATE users SET balance_cents = balance_cents + {PH} WHERE id = {PH}",
            (amount_cents, user_id)
        )
        return True


def mark_stripe_event_processed(stripe_event_id, event_type, user_id=None, amount_cents=0):
    """
    Record a Stripe webhook event exactly once.

    Returns True when the event is newly recorded and should be applied.
    Returns False when the event was already processed.
    """
    with get_db() as conn:
        existing = conn.execute(
            f"SELECT id FROM stripe_webhook_events WHERE stripe_event_id = {PH}",
            (stripe_event_id,)
        ).fetchone()
        if existing:
            return False

        conn.execute(
            f"INSERT INTO stripe_webhook_events "
            f"(id, stripe_event_id, event_type, user_id, amount_cents, created_at) "
            f"VALUES ({PH},{PH},{PH},{PH},{PH},{PH})",
            (
                str(uuid.uuid4()),
                stripe_event_id,
                event_type,
                user_id,
                amount_cents,
                datetime.now(timezone.utc).isoformat(),
            )
        )
        return True


def deduct_credits(user_id, amount_cents):
    with get_db() as conn:
        conn.execute(
            f"UPDATE users SET balance_cents = CASE WHEN balance_cents - {PH} < 0 THEN 0 "
            f"ELSE balance_cents - {PH} END WHERE id = {PH}",
            (amount_cents, amount_cents, user_id)
        )


def log_usage(user_id, action_type, input_tokens, output_tokens, model,
              report_id=None, simulation_id=None):
    total = input_tokens + output_tokens
    cost = _estimate_usage_cost_cents(input_tokens, output_tokens)
    with get_db() as conn:
        conn.execute(
            f"INSERT INTO usage_log "
            f"(id, user_id, action_type, input_tokens, output_tokens, total_tokens, "
            f"estimated_cost_cents, report_id, simulation_id, model, created_at) "
            f"VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
            (str(uuid.uuid4()), user_id, action_type, input_tokens, output_tokens,
             total, cost, report_id, simulation_id, model,
             datetime.now(timezone.utc).isoformat())
        )


def get_user_usage(user_id, days=30):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM usage_log WHERE user_id = {PH} AND created_at > {PH} "
            f"ORDER BY created_at DESC",
            (user_id, cutoff)
        ).fetchall()
        return [dict(r) for r in rows]


def get_user_total_cost(user_id):
    with get_db() as conn:
        row = conn.execute(
            f"SELECT SUM(estimated_cost_cents) as total FROM usage_log WHERE user_id = {PH}",
            (user_id,)
        ).fetchone()
        return row['total'] or 0


def get_user_report_count(user_id):
    with get_db() as conn:
        row = conn.execute(
            f"SELECT COUNT(*) as cnt FROM usage_log "
            f"WHERE user_id = {PH} AND action_type = 'report_generate'",
            (user_id,)
        ).fetchone()
        return row['cnt'] if row else 0


def get_report_cost(user_id):
    user = get_user_by_id(user_id)
    if not user:
        return REPORT_PRICE_CENTS
    with get_db() as conn:
        slot_count = _get_report_slot_count(conn, user_id)
    return _get_report_cost_for_slot_count(user, slot_count)


def reserve_report_generation(user_id, report_id=None, simulation_id=None):
    """
    Atomically reserve a report generation slot and pre-charge paid usage.

    A pending usage row is created for every accepted generation request,
    including free/trial/admin requests, so concurrent requests cannot reuse the
    same free slot before the report finishes.
    """
    with get_db() as conn:
        user_row = conn.execute(
            f"SELECT * FROM users WHERE id = {PH}", (user_id,)
        ).fetchone()
        if not user_row:
            return False, 0, 'user_not_found', None

        user = dict(user_row)
        slot_count = _get_report_slot_count(conn, user_id)
        cost = _get_report_cost_for_slot_count(user, slot_count)

        if user.get('role') in ('admin', 'demo'):
            reason = 'admin'
        else:
            in_trial, _, _ = _get_trial_status(user)
            if in_trial:
                reason = 'trial'
            elif cost == 0:
                reason = 'free_report'
            else:
                reason = 'paid'

        if cost > 0:
            cursor = conn.execute(
                f"UPDATE users SET balance_cents = balance_cents - {PH} "
                f"WHERE id = {PH} AND balance_cents >= {PH}",
                (cost, user_id, cost)
            )
            if cursor.rowcount == 0:
                return False, cost, 'insufficient_funds', None

        reservation_id = str(uuid.uuid4())
        conn.execute(
            f"INSERT INTO usage_log "
            f"(id, user_id, action_type, input_tokens, output_tokens, total_tokens, "
            f"estimated_cost_cents, report_id, simulation_id, model, created_at) "
            f"VALUES ({PH},{PH},'report_generate_pending',0,0,0,{PH},{PH},{PH},{PH},{PH})",
            (
                reservation_id,
                user_id,
                cost,
                report_id,
                simulation_id,
                'billing_reservation',
                datetime.now(timezone.utc).isoformat(),
            )
        )
        return True, cost, reason, reservation_id


def finalize_report_generation_reservation(
    reservation_id,
    user_id,
    usage=None,
    report_id=None,
    simulation_id=None,
    model=None,
):
    """Finalize a pending report reservation into a completed usage row."""
    usage = usage or {}
    input_tokens = usage.get('prompt_tokens', 0)
    output_tokens = usage.get('completion_tokens', 0)
    total_tokens = input_tokens + output_tokens
    estimated_cost = _estimate_usage_cost_cents(input_tokens, output_tokens)

    with get_db() as conn:
        cursor = conn.execute(
            f"UPDATE usage_log SET "
            f"action_type = 'report_generate', "
            f"input_tokens = {PH}, "
            f"output_tokens = {PH}, "
            f"total_tokens = {PH}, "
            f"estimated_cost_cents = {PH}, "
            f"report_id = {PH}, "
            f"simulation_id = {PH}, "
            f"model = {PH} "
            f"WHERE id = {PH} AND user_id = {PH} AND action_type = 'report_generate_pending'",
            (
                input_tokens,
                output_tokens,
                total_tokens,
                estimated_cost,
                report_id,
                simulation_id,
                model or '',
                reservation_id,
                user_id,
            )
        )
        return cursor.rowcount > 0


def find_pending_report_generation_reservation(user_id, report_id=None, simulation_id=None):
    """Find a pending report-generation reservation by user and report context."""
    if not report_id and not simulation_id:
        return None

    clauses = [f"user_id = {PH}", "action_type = 'report_generate_pending'"]
    params = [user_id]

    if report_id:
        clauses.append(f"report_id = {PH}")
        params.append(report_id)
    if simulation_id:
        clauses.append(f"simulation_id = {PH}")
        params.append(simulation_id)

    sql = (
        "SELECT id FROM usage_log "
        f"WHERE {' AND '.join(clauses)} "
        "ORDER BY created_at DESC LIMIT 1"
    )

    with get_db() as conn:
        row = conn.execute(sql, tuple(params)).fetchone()
        return row['id'] if row else None


def release_report_generation_reservation(reservation_id, user_id):
    """
    Release a pending reservation and refund any pre-charged balance.

    Returns the refunded amount in cents.
    """
    with get_db() as conn:
        row = conn.execute(
            f"SELECT estimated_cost_cents FROM usage_log "
            f"WHERE id = {PH} AND user_id = {PH} AND action_type = 'report_generate_pending'",
            (reservation_id, user_id)
        ).fetchone()
        if not row:
            return 0

        reserved_amount = row['estimated_cost_cents'] or 0
        if reserved_amount > 0:
            conn.execute(
                f"UPDATE users SET balance_cents = balance_cents + {PH} WHERE id = {PH}",
                (reserved_amount, user_id)
            )

        conn.execute(
            f"DELETE FROM usage_log WHERE id = {PH} AND user_id = {PH} AND action_type = 'report_generate_pending'",
            (reservation_id, user_id)
        )
        return reserved_amount


def can_user_generate(user_id):
    user = get_user_by_id(user_id)
    if not user:
        return False, 0, 'user_not_found'
    if user.get('role') in ('admin', 'demo'):
        return True, 0, 'admin'
    in_trial, _, _ = _get_trial_status(user)
    if in_trial:
        return True, 0, 'trial'
    cost = get_report_cost(user_id)
    if cost == 0:
        return True, 0, 'free_report'
    balance = get_balance(user_id)
    if balance >= cost:
        return True, cost, 'paid'
    return False, cost, 'insufficient_funds'


def get_user_billing_status(user_id):
    user = get_user_by_id(user_id)
    if not user:
        return {'can_generate': False, 'error': 'user_not_found'}

    is_admin = user.get('role') in ('admin', 'demo')
    in_trial, trial_ends_at, trial_days_left = _get_trial_status(user)

    balance_cents = user.get('balance_cents') or 0
    report_count = get_user_report_count(user_id)
    next_report_cost = get_report_cost(user_id)
    can_generate = can_user_generate(user_id)[0]

    return {
        'can_generate': can_generate,
        'is_trial': in_trial,
        'trial_ends_at': trial_ends_at,
        'trial_days_left': trial_days_left,
        'balance_cents': balance_cents,
        'report_count': report_count,
        'next_report_cost': next_report_cost,
    }

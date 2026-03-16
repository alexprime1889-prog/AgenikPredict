"""
Authentication API endpoints — magic link flow

POST /api/auth/request   — request a magic link (send email)
GET  /api/auth/verify     — verify token, return JWT
GET  /api/auth/me         — get current user from JWT
POST /api/auth/demo       — instant login as demo user
"""

import os
import time
import json
import hmac
import hashlib
import base64
import secrets as _secrets
from functools import wraps

from flask import request, jsonify, g

from . import auth_bp
from ..models.user import (
    get_user_by_email, get_user_by_id, create_user,
    create_magic_link, verify_magic_link, seed_demo,
    is_in_trial, get_user_billing_status, get_user_usage,
)
from ..services.email_service import send_magic_link_email
from ..utils.logger import get_logger

logger = get_logger('agenikpredict.auth')

_generated_secret = _secrets.token_hex(32)
JWT_SECRET = os.environ.get('JWT_SECRET', os.environ.get('SECRET_KEY', ''))
if not JWT_SECRET or JWT_SECRET in ('agenikpredict-jwt-secret', 'agenikpredict-secret-key'):
    JWT_SECRET = _generated_secret
    logger.warning("JWT_SECRET not set — using auto-generated secret (tokens will invalidate on restart)")
JWT_TTL = 60 * 60 * 24 * 7  # 7 days


# ── Minimal JWT (no dependency needed) ──

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    s += '=' * padding
    return base64.urlsafe_b64decode(s)


def create_jwt(user_id: str, email: str, role: str, plan: str,
               trial_ends_at: str | None = None, in_trial: bool = False) -> str:
    """Create a simple HS256 JWT"""
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url_encode(json.dumps({
        "sub": user_id,
        "email": email,
        "role": role,
        "plan": plan,
        "trial_ends_at": trial_ends_at,
        "is_trial": in_trial,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_TTL,
    }).encode())
    signature = hmac.new(
        JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256
    ).digest()
    sig_b64 = _b64url_encode(signature)
    return f"{header}.{payload}.{sig_b64}"


def decode_jwt(token: str) -> dict | None:
    """Decode and verify JWT. Returns payload dict or None."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None

        header, payload, sig = parts
        expected_sig = hmac.new(
            JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256
        ).digest()

        if not hmac.compare_digest(_b64url_decode(sig), expected_sig):
            return None

        data = json.loads(_b64url_decode(payload))

        if data.get('exp', 0) < time.time():
            return None

        return data
    except Exception:
        return None


# ── Auth middleware ──

def require_auth(f):
    """Decorator: require valid JWT in Authorization header"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"success": False, "error": "Missing authorization token"}), 401

        token = auth_header[7:]
        payload = decode_jwt(token)
        if not payload:
            return jsonify({"success": False, "error": "Invalid or expired token"}), 401

        g.user_id = payload['sub']
        g.user_email = payload['email']
        g.user_role = payload['role']
        g.user_plan = payload['plan']
        return f(*args, **kwargs)
    return decorated


def optional_auth(f):
    """Decorator: parse JWT if present, but don't require it"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            payload = decode_jwt(auth_header[7:])
            if payload:
                g.user_id = payload['sub']
                g.user_email = payload['email']
                g.user_role = payload['role']
                g.user_plan = payload['plan']
        return f(*args, **kwargs)
    return decorated


# ── Endpoints ──

@auth_bp.route('/request', methods=['POST'])
def request_magic_link():
    """
    Request a magic link. Creates user if new.
    Body: { "email": "user@example.com" }
    """
    data = request.get_json(silent=True)
    if not data or not data.get('email'):
        return jsonify({"success": False, "error": "Email is required"}), 400

    email = data['email'].lower().strip()

    # Basic email validation
    if '@' not in email or '.' not in email.split('@')[-1]:
        return jsonify({"success": False, "error": "Invalid email address"}), 400

    # Find or create user
    user = get_user_by_email(email)
    if not user:
        user = create_user(email)
        logger.info(f"New user registered: {email}")

    # Create magic link
    token = create_magic_link(user['id'])

    # Send email
    sent = send_magic_link_email(email, token, user.get('name', ''))

    if not sent:
        return jsonify({"success": False, "error": "Failed to send email. Please try again."}), 500

    return jsonify({
        "success": True,
        "message": "Magic link sent! Check your inbox.",
    })


@auth_bp.route('/verify', methods=['GET'])
def verify_token():
    """
    Verify a magic link token and return a JWT.
    Query: ?token=xxx
    """
    token = request.args.get('token', '').strip()
    if not token:
        return jsonify({"success": False, "error": "Token is required"}), 400

    user = verify_magic_link(token)
    if not user:
        return jsonify({"success": False, "error": "Invalid or expired link. Please request a new one."}), 401

    in_trial = is_in_trial(user['id'])
    jwt_token = create_jwt(
        user['id'], user['email'], user['role'], user['plan'],
        trial_ends_at=user.get('trial_ends_at'),
        in_trial=in_trial,
    )

    return jsonify({
        "success": True,
        "token": jwt_token,
        "user": {
            "id": user['id'],
            "email": user['email'],
            "name": user['name'],
            "role": user['role'],
            "plan": user['plan'],
            "trial_ends_at": user.get('trial_ends_at'),
            "is_trial": in_trial,
        },
    })


@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_current_user():
    """Get current authenticated user profile"""
    user = get_user_by_id(g.user_id)
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    return jsonify({
        "success": True,
        "user": {
            "id": user['id'],
            "email": user['email'],
            "name": user['name'],
            "role": user['role'],
            "plan": user['plan'],
            "created_at": user['created_at'],
            "last_login_at": user['last_login_at'],
        },
    })


@auth_bp.route('/demo', methods=['POST'])
def demo_login():
    """Instant login as demo user (no email required)"""
    demo_id = seed_demo()
    user = get_user_by_id(demo_id)

    in_trial = is_in_trial(user['id'])
    jwt_token = create_jwt(
        user['id'], user['email'], user['role'], user['plan'],
        trial_ends_at=user.get('trial_ends_at'),
        in_trial=in_trial,
    )

    return jsonify({
        "success": True,
        "token": jwt_token,
        "user": {
            "id": user['id'],
            "email": user['email'],
            "name": user['name'],
            "role": user['role'],
            "plan": user['plan'],
            "trial_ends_at": user.get('trial_ends_at'),
            "is_trial": in_trial,
        },
    })


@auth_bp.route('/billing-status', methods=['GET'])
@require_auth
def billing_status():
    """Get billing status for the current authenticated user"""
    status = get_user_billing_status(g.user_id)
    return jsonify({"success": True, "data": status})


@auth_bp.route('/usage', methods=['GET'])
@require_auth
def get_usage():
    """Get usage history for the current authenticated user (last 30 days)"""
    usage = get_user_usage(g.user_id, days=30)
    return jsonify({"success": True, "data": usage})

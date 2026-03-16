"""
Email service for sending magic links via Resend.
Falls back to console logging when RESEND_API_KEY is not configured.
"""

import os
import requests

from ..utils.logger import get_logger

logger = get_logger('agenikpredict.email')

RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
RESEND_FROM = os.environ.get('RESEND_FROM_EMAIL', 'AgenikPredict <noreply@agenikpredict.com>')
APP_URL = os.environ.get('APP_URL', 'http://localhost:3000')


def send_magic_link_email(to_email, token, user_name=""):
    """
    Send a magic link email to the user.
    Returns True on success.
    """
    magic_url = f"{APP_URL}/auth/verify?token={token}"

    if not RESEND_API_KEY:
        # Development fallback: log to console
        logger.warning("=" * 60)
        logger.warning("RESEND_API_KEY not set — printing magic link to console:")
        logger.warning(f"  Email: {to_email}")
        logger.warning(f"  Magic Link: {magic_url}")
        logger.warning("=" * 60)
        return True

    greeting = f"Hi {user_name}," if user_name else "Hi,"

    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 480px; margin: 0 auto; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="color: #1B2A4A; font-size: 24px; margin: 0;">AgenikPredict</h1>
            <p style="color: #888; font-size: 13px; margin: 4px 0 0;">Multi-Agent Prediction Engine</p>
        </div>

        <p style="color: #333; font-size: 16px; line-height: 1.6;">{greeting}</p>
        <p style="color: #333; font-size: 16px; line-height: 1.6;">Click the button below to sign in to AgenikPredict. This link expires in 10 minutes.</p>

        <div style="text-align: center; margin: 32px 0;">
            <a href="{magic_url}" style="display: inline-block; background: #2E75B6; color: #fff; text-decoration: none; padding: 14px 40px; border-radius: 8px; font-size: 16px; font-weight: 600;">
                Sign In
            </a>
        </div>

        <p style="color: #888; font-size: 13px; line-height: 1.5;">
            If the button doesn't work, copy and paste this link into your browser:<br>
            <a href="{magic_url}" style="color: #2E75B6; word-break: break-all;">{magic_url}</a>
        </p>

        <hr style="border: none; border-top: 1px solid #eee; margin: 32px 0;">
        <p style="color: #aaa; font-size: 12px; text-align: center;">
            If you didn't request this email, you can safely ignore it.<br>
            &copy; {__import__('datetime').datetime.now().year} Manogrand Inc
        </p>
    </div>
    """

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": RESEND_FROM,
                "to": [to_email],
                "subject": "Sign in to AgenikPredict",
                "html": html_body,
            },
            timeout=10,
        )

        if resp.status_code in (200, 201):
            logger.info(f"Magic link email sent to {to_email}")
            return True
        else:
            logger.error(f"Resend API error: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False

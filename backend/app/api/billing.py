"""
Billing API routes -- Stripe checkout + webhook + balance management
"""

import stripe
from flask import request, jsonify, g

from . import billing_bp
from .auth import require_auth
from ..config import Config
from ..models.user import add_credits
from ..utils.logger import get_logger

logger = get_logger('agenikpredict.api.billing')


@billing_bp.route('/prices', methods=['GET'])
def get_prices():
    """Return available credit packs and Stripe publishable key"""
    return jsonify({
        'success': True,
        'data': {
            'packs': [
                {'amount': 500, 'label': '$5', 'price_id': Config.STRIPE_PRICE_5},
                {'amount': 2000, 'label': '$20', 'price_id': Config.STRIPE_PRICE_20},
                {'amount': 5000, 'label': '$50', 'price_id': Config.STRIPE_PRICE_50},
                {'amount': 10000, 'label': '$100', 'price_id': Config.STRIPE_PRICE_100},
            ],
            'publishable_key': Config.STRIPE_PUBLISHABLE_KEY,
        },
    })


@billing_bp.route('/checkout', methods=['POST'])
@require_auth
def create_checkout():
    """Create Stripe checkout session for credit purchase"""
    data = request.get_json() or {}
    price_id = data.get('price_id')

    if not price_id:
        return jsonify({'success': False, 'error': 'price_id required'}), 400

    if not Config.STRIPE_SECRET_KEY:
        return jsonify({'success': False, 'error': 'Stripe not configured'}), 503

    stripe.api_key = Config.STRIPE_SECRET_KEY

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='payment',
            success_url=f'{Config.APP_URL}/?payment=success',
            cancel_url=f'{Config.APP_URL}/?payment=cancelled',
            metadata={
                'user_id': g.user_id,
                'user_email': g.user_email,
            },
        )
        return jsonify({
            'success': True,
            'data': {'checkout_url': session.url, 'session_id': session.id},
        })
    except Exception as e:
        logger.error(f'Stripe checkout error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@billing_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events (called by Stripe, no JWT auth)"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')

    if not Config.STRIPE_WEBHOOK_SECRET:
        return jsonify({'error': 'Webhook not configured'}), 503

    stripe.api_key = Config.STRIPE_SECRET_KEY

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, Config.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({'error': 'Invalid signature'}), 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session.get('metadata', {}).get('user_id')
        amount_cents = session.get('amount_total', 0)

        if user_id and amount_cents > 0:
            add_credits(user_id, amount_cents)
            logger.info(
                f'Credits added via Stripe: user={user_id}, amount={amount_cents} cents'
            )

    return jsonify({'received': True}), 200

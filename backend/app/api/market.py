"""
Market Data API routes.
Provides ticker detection, quote fetching, and text enrichment endpoints.
"""

from flask import request, jsonify
from . import market_bp
from ..services.market_data import MarketDataService
from ..utils.logger import get_logger

logger = get_logger('agenikpredict.api.market')

_service = None


def _get_service():
    global _service
    if _service is None:
        _service = MarketDataService()
    return _service


@market_bp.route('/status', methods=['GET'])
def market_status():
    """Check if market data service is available."""
    service = _get_service()
    return jsonify({
        "success": True,
        "data": {
            "available": service.is_available,
            "provider": "twelvedata" if service.is_available else None
        }
    })


@market_bp.route('/detect-tickers', methods=['POST'])
def detect_tickers():
    """Detect stock ticker symbols in text."""
    data = request.get_json() or {}
    text = data.get('text', '')

    if not text:
        return jsonify({"success": False, "error": "Please provide text"}), 400

    service = _get_service()
    tickers = service.detect_tickers(text)

    return jsonify({
        "success": True,
        "data": {
            "tickers": tickers,
            "count": len(tickers)
        }
    })


@market_bp.route('/quote/<symbol>', methods=['GET'])
def get_quote(symbol):
    """Get real-time quote for a symbol."""
    service = _get_service()

    if not service.is_available:
        return jsonify({"success": False, "error": "Market data service not configured"}), 503

    quote = service.fetch_quote(symbol.upper())
    if not quote:
        return jsonify({"success": False, "error": f"Could not fetch quote for {symbol}"}), 404

    return jsonify({
        "success": True,
        "data": quote
    })


@market_bp.route('/time-series/<symbol>', methods=['GET'])
def get_time_series(symbol):
    """Get historical time series for a symbol."""
    service = _get_service()

    if not service.is_available:
        return jsonify({"success": False, "error": "Market data service not configured"}), 503

    interval = request.args.get('interval', '1day')
    outputsize = int(request.args.get('outputsize', 30))

    data = service.fetch_time_series(symbol.upper(), interval=interval, outputsize=outputsize)
    if not data:
        return jsonify({"success": False, "error": f"Could not fetch time series for {symbol}"}), 404

    return jsonify({
        "success": True,
        "data": data
    })


@market_bp.route('/enrich', methods=['POST'])
def enrich_text():
    """Detect tickers in text and enrich with market data."""
    data = request.get_json() or {}
    text = data.get('text', '')

    if not text:
        return jsonify({"success": False, "error": "Please provide text"}), 400

    service = _get_service()
    enriched = service.enrich_text_with_market_data(text)
    tickers = service.detect_tickers(text)

    return jsonify({
        "success": True,
        "data": {
            "enriched_text": enriched,
            "detected_tickers": tickers,
            "enriched": enriched != text
        }
    })


@market_bp.route('/summary', methods=['POST'])
def market_summary():
    """Get quotes for multiple symbols."""
    data = request.get_json() or {}
    symbols = data.get('symbols', [])

    if not symbols:
        return jsonify({"success": False, "error": "Please provide symbols array"}), 400

    service = _get_service()

    if not service.is_available:
        return jsonify({"success": False, "error": "Market data service not configured"}), 503

    summary = service.get_market_summary(symbols)

    return jsonify({
        "success": True,
        "data": {
            "quotes": summary,
            "count": len(summary)
        }
    })

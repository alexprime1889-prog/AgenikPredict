"""
Market Data Service — Twelve Data integration for AgenikPredict.

Provides ticker detection in text, real-time quotes, time series,
and text enrichment with market context for the simulation pipeline.
"""

import time
from typing import List, Dict, Optional
import reticker
from twelvedata import TDClient

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('agenikpredict.services.market_data')


class MarketDataService:
    """Service for fetching and enriching data from financial markets."""

    def __init__(self):
        api_key = Config.TWELVE_DATA_API_KEY
        if not api_key:
            logger.warning("TWELVE_DATA_API_KEY not set — market data features disabled")
            self._client = None
        else:
            self._client = TDClient(apikey=api_key)
            logger.info("MarketDataService initialized with Twelve Data")
        self._ticker_extractor = reticker.TickerExtractor()
        # Simple in-memory cache: symbol -> (timestamp, data)
        self._quote_cache: Dict[str, tuple] = {}
        self._cache_ttl = 300  # 5 minutes

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def detect_tickers(self, text: str) -> List[str]:
        """Extract stock ticker symbols from text using reticker."""
        if not text:
            return []
        tickers = self._ticker_extractor.extract(text)
        # Filter out common false positives (short words that aren't tickers)
        false_positives = {
            'I', 'A', 'AI', 'AM', 'AN', 'AS', 'AT', 'BE', 'BY', 'DO',
            'GO', 'HE', 'IF', 'IN', 'IS', 'IT', 'ME', 'MY', 'NO', 'OF',
            'OK', 'ON', 'OR', 'SO', 'TO', 'UP', 'US', 'WE', 'CEO', 'USA',
            'UK', 'EU', 'UN', 'GDP', 'API', 'CEO', 'CFO', 'CTO', 'COO',
            'HR', 'PR', 'VP', 'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT',
            'YOU', 'ALL', 'CAN', 'HER', 'WAS', 'ONE', 'OUR', 'OUT', 'HAS',
            'PDF', 'URL', 'LLM', 'GPT', 'RAG', 'ETF',
        }
        return [t for t in tickers if t not in false_positives and len(t) >= 2]

    def fetch_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch real-time quote for a symbol. Returns None if unavailable."""
        if not self._client:
            return None

        # Check cache
        cached = self._quote_cache.get(symbol)
        if cached and (time.time() - cached[0]) < self._cache_ttl:
            return cached[1]

        try:
            result = self._client.quote(symbol=symbol).as_json()
            if result and 'code' not in result:  # No error
                self._quote_cache[symbol] = (time.time(), result)
                logger.info(f"Quote fetched: {symbol} = {result.get('close', 'N/A')}")
                return result
            else:
                logger.warning(f"Quote error for {symbol}: {result}")
                return None
        except Exception as e:
            logger.error(f"Failed to fetch quote for {symbol}: {e}")
            return None

    def fetch_time_series(self, symbol: str, interval: str = "1day", outputsize: int = 30) -> Optional[Dict]:
        """Fetch historical time series for a symbol."""
        if not self._client:
            return None
        try:
            result = self._client.time_series(
                symbol=symbol,
                interval=interval,
                outputsize=outputsize
            ).as_json()
            if result and 'code' not in result:
                logger.info(f"Time series fetched: {symbol}, {interval}, {outputsize} bars")
                return result
            else:
                logger.warning(f"Time series error for {symbol}: {result}")
                return None
        except Exception as e:
            logger.error(f"Failed to fetch time series for {symbol}: {e}")
            return None

    def enrich_text_with_market_data(self, text: str) -> str:
        """
        Detect tickers in text, fetch quotes, and append market context.
        Returns the original text + appended market data paragraphs.
        """
        if not self._client:
            return text

        tickers = self.detect_tickers(text)
        if not tickers:
            return text

        logger.info(f"Detected {len(tickers)} tickers in text: {tickers}")

        market_sections = []
        for ticker in tickers[:20]:  # Limit to 20 tickers
            quote = self.fetch_quote(ticker)
            if not quote:
                continue

            section = self._format_quote_as_text(ticker, quote)
            if section:
                market_sections.append(section)

        if not market_sections:
            return text

        enrichment = "\n\n--- LIVE MARKET DATA ---\n\n" + "\n\n".join(market_sections)
        return text + enrichment

    def _format_quote_as_text(self, symbol: str, quote: Dict) -> Optional[str]:
        """Format a quote as a human-readable text paragraph for graph ingestion."""
        try:
            name = quote.get('name', symbol)
            close = quote.get('close', 'N/A')
            change = quote.get('change', 'N/A')
            pct = quote.get('percent_change', 'N/A')
            volume = quote.get('volume', 'N/A')
            exchange = quote.get('exchange', 'N/A')
            currency = quote.get('currency', 'USD')
            prev_close = quote.get('previous_close', 'N/A')

            week52 = quote.get('fifty_two_week', {})
            high52 = week52.get('high', 'N/A')
            low52 = week52.get('low', 'N/A')

            return (
                f"{name} ({symbol}) — Listed on {exchange}. "
                f"Current price: {close} {currency} (change: {change}, {pct}%). "
                f"Previous close: {prev_close} {currency}. Volume: {volume}. "
                f"52-week range: {low52} — {high52} {currency}."
            )
        except Exception as e:
            logger.error(f"Failed to format quote for {symbol}: {e}")
            return None

    def get_market_summary(self, symbols: List[str]) -> List[Dict]:
        """Get quotes for multiple symbols. Returns list of quote dicts."""
        results = []
        for symbol in symbols[:20]:
            quote = self.fetch_quote(symbol)
            if quote:
                results.append({
                    'symbol': symbol,
                    'name': quote.get('name', symbol),
                    'price': quote.get('close'),
                    'change': quote.get('change'),
                    'percent_change': quote.get('percent_change'),
                    'volume': quote.get('volume'),
                    'exchange': quote.get('exchange'),
                    'currency': quote.get('currency'),
                })
        return results

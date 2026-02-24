import time
from typing import List, Dict
from core.tools.binance_futures import BinanceFutures
class CandlesFetcher:
    """
    Fetches klines (candles) from Binance Futures.
    Provides lightweight caching to reduce API load.
    """
    def __init__(self):
        self.client = BinanceFutures()
        self._cache = {}
        self._cache_time = {}
        self.cache_ttl = 30  # seconds
    def _cache_key(self, symbol: str, interval: str, limit: int):
        return f"{symbol}_{interval}_{limit}"
    def get_candles(self, symbol: str, interval: str = "1m", limit: int = 200) -> List[Dict]:
        key = self._cache_key(symbol, interval, limit)
        now = time.time()
        if key in self._cache:
            if now - self._cache_time.get(key, 0) < self.cache_ttl:
                return self._cache[key]
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        raw = self.client._get("/fapi/v1/klines", params)
        if not raw:
            return []
        candles = []
        for c in raw:
            try:
                candles.append({
                    "open_time": c[0],
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4]),
                    "volume": float(c[5]),
                    "close_time": c[6]
                })
            except (ValueError, TypeError):
                continue
        self._cache[key] = candles
        self._cache_time[key] = now
        return candles
_

import time
from typing import Dict
from core.tools.binance_futures import BinanceFutures
class DerivativesData:
    def __init__(self):
        self.client = BinanceFutures()
        self._funding_cache: Dict[str, dict] = {}
        self._oi_cache: Dict[str, dict] = {}
        self.cache_ttl = 60  # 1 minute
    def _cached(self, cache: dict, symbol: str):
        entry = cache.get(symbol)
        if not entry:
            return None
        if time.time() - entry.get("ts", 0) > self.cache_ttl:
            return None
        return entry.get("data")
    def get_funding_rate(self, symbol: str) -> float:
        cached = self._cached(self._funding_cache, symbol)
        if cached is not None:
            return cached
        data = self.client._get(
            "/fapi/v1/premiumIndex",
            {"symbol": symbol}
        )
        if not data:
            return 0.0
        funding = float(data.get("lastFundingRate", 0.0))
        self._funding_cache[symbol] = {
            "data": funding,
            "ts": time.time()
        }
        return funding
    def get_open_interest(self, symbol: str) -> float:
        cached = self._cached(self._oi_cache, symbol)
        if cached is not None:
            return cached
        data = self.client._get(
            "/fapi/v1/openInterest",
            {"symbol": symbol}
        )
        if not data:
            return 0.0
        oi = float(data.get("openInterest", 0.0))
        self._oi_cache[symbol] = {
            "data": oi,
            "ts": time.time()
        }
        return oi
_

import time
from dataclasses import dataclass
from typing import List
from core.tools.binance_futures import BinanceFutures
@dataclass
class UniverseConfig:
    top_n: int = 20
    refresh_seconds: int = 300  # refresh every 5 minutes
class MarketUniverse:
    def __init__(self, cfg: UniverseConfig | None = None):
        self.cfg = cfg or UniverseConfig()
        self.client = BinanceFutures()
        self._cache: List[str] = []
        self._last_refresh = 0
    def _all_usdt_perp_symbols(self) -> set[str]:
        info = self.client.exchange_info()
        if not info or "symbols" not in info:
            return set()
        syms = set()
        for s in info.get("symbols", []):
            if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING":
                syms.add(s["symbol"])
        return syms
    def _tickers_24h(self) -> list[dict]:
        # 24h rolling window ticker stats
        return self.client._get("/fapi/v1/ticker/24hr") or []
    def top_symbols(self) -> List[str]:
        now = int(time.time())
        if self._cache and (now - self._last_refresh) < self.cfg.refresh_seconds:
            return self._cache
        allowed = self._all_usdt_perp_symbols()
        tickers = self._tickers_24h()
        scored = []
        for t in tickers:
            sym = t.get("symbol")
            if sym not in allowed:
                continue
            # quoteVolume = حجم التداول بالدولار تقريباً
            try:
                qv = float(t.get("quoteVolume", 0.0))
            except (ValueError, TypeError):
                qv = 0.0
            scored.append((qv, sym))
        scored.sort(reverse=True, key=lambda x: x[0])
        top = [sym for _, sym in scored[: self.cfg.top_n]]
        self._cache = top
        self._last_refresh = now
        return top
_

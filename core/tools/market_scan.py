from typing import List, Dict
from core.tools.binance_futures import BinanceFutures
from core.tools.momentum_engine import MomentumEngine

# Symbols known to have issues (delisted, settlement-only, or restricted)
BLACKLISTED_SYMBOLS = set()

class MarketScanner:
    def __init__(self, policy: dict):
        self.policy = policy
        self.client = BinanceFutures(self.policy.get('binance_api_key'), self.policy.get('binance_api_secret'))
        self.momentum_engine = MomentumEngine()
        self._valid_symbols = set()  # Cache of valid TRADING symbols

    def _load_valid_symbols(self):
        """Load only symbols with status=TRADING from exchange info."""
        try:
            info = self.client._get("/fapi/v1/exchangeInfo")
            if info:
                self._valid_symbols = {
                    s['symbol'] for s in info.get('symbols', [])
                    if s.get('status') == 'TRADING' and s['symbol'].endswith('USDT')
                }
                print(f"[MarketScanner] Loaded {len(self._valid_symbols)} valid USDT trading symbols", flush=True)
        except Exception as e:
            print(f"[MarketScanner] Could not load exchange info: {e}", flush=True)

    def scan_for_candidates(self) -> List[Dict]:
        # Refresh valid symbols list if empty
        if not self._valid_symbols:
            self._load_valid_symbols()

        print("Fetching all tickers...", flush=True)
        tickers = self.client.get_all_tickers()
        if not tickers:
            print("Could not fetch tickers.", flush=True)
            return []

        # Filter: only USDT pairs that are actively TRADING
        usdt_tickers = [
            t for t in tickers
            if t['symbol'].endswith('USDT')
            and t['symbol'] not in BLACKLISTED_SYMBOLS
            and (not self._valid_symbols or t['symbol'] in self._valid_symbols)
        ]

        candidates = []
        print(f"Found {len(usdt_tickers)} valid USDT tickers. Analyzing...", flush=True)

        for ticker in usdt_tickers:
            symbol = ticker['symbol']
            print(f"Fetching candles for {symbol}...", flush=True)
            candles = self.client.get_candles(symbol, '15m')
            if not candles or len(candles) < 21:
                continue
            analysis = self.momentum_engine.analyze(candles)
            score = analysis.get('score', 0)
            if score >= self.policy.get('scanner', {}).get('entry_threshold', 3.5):
                candidates.append({
                    'symbol': symbol,
                    'score': score,
                    'direction': analysis.get('direction'),
                    'candles': candles
                })
                print(f"*** Candidate found: {symbol} (Score: {score}) ***", flush=True)
        return candidates

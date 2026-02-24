from typing import List, Dict
from core.tools.binance_futures import BinanceFutures
from core.tools.momentum_engine import MomentumEngine
class MarketScanner:
    def __init__(self, policy: dict):
        self.policy = policy
        self.client = BinanceFutures(self.policy.get('binance_api_key'), self.policy.get('binance_api_secret'))
        self.momentum_engine = MomentumEngine()
    def scan_for_candidates(self) -> List[Dict]:
        print("Fetching all tickers...")
        tickers = self.client.get_all_tickers()
        if not tickers:
            print("Could not fetch tickers.")
            return []
        candidates = []
        print(f"Found {len(tickers)} tickers. Analyzing...")
        # For testing, we'll only scan a few tickers to speed things up
        for ticker in tickers[:10]: # Limiting to 10 for the test run
            symbol = ticker['symbol']
            if not symbol.endswith('USDT'):
                continue
            print(f"Fetching candles for {symbol}...")
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
                print(f"*** Candidate found: {symbol} (Score: {score}) ***")
        return candidates

import time
from datetime import datetime
from core.brain.memory import Memory
from core.tools.risk_governor import RiskGovernor
from core.tools.market_scan import MarketScanner
from core.tools.weighted_brain import WeightedBrain
from core.tools.order_router import OrderRouter
def main_loop():
    print(f"[{datetime.now()}] MohammedCore Worker started.")
    from pathlib import Path
    memory = Memory(data_path=Path("storage/state.json"))
    import json
    with open("storage/policy.json", "r") as f:
        policy = json.load(f)
    scanner = MarketScanner(policy)
    brain = WeightedBrain(policy)
    governor = RiskGovernor(policy, memory)
    router = OrderRouter(policy, memory)
    while True:
        print(f"[{datetime.now()}] Scanning market...")
        candidates = scanner.scan_for_candidates()
        if not candidates:
            print(f"[{datetime.now()}] No candidates found. Waiting for next cycle.")
            time.sleep(60)
            continue
        for candidate in candidates:
            symbol = candidate['symbol']
            print(f"[{datetime.now()}] Analyzing candidate: {symbol}")
            # 1. Brain Analysis
            from core.tools.momentum_strategy import MomentumStrategy
            from core.tools.pattern_strategy import PatternStrategy

            momentum_strategy = MomentumStrategy()
            pattern_strategy = PatternStrategy()

            scores = [
                momentum_strategy.analyze(candidate['candles']),
                pattern_strategy.analyze(candidate['candles'])
            ]

            brain_dump = brain.evaluate(scores)
            # 2. Risk Governor Check
            signal = governor.validate_trade(symbol, brain_dump, candidate)
            if not signal.approved:
                print(f"[{datetime.now()}] Trade REJECTED for {symbol}: {signal.reason}")
                continue
            # 3. Route Order
            print(f"[{datetime.now()}] Trade APPROVED for {symbol}. Routing order...")
            result = router.route(signal)
            if result['success']:
                print(f"[{datetime.now()}] Order PLACED for {symbol}: {result['status']}")
            else:
                print(f"[{datetime.now()}] Order FAILED for {symbol}: {result['status']}")
        # Wait before next full scan
        print(f"[{datetime.now()}] Scan cycle complete. Waiting...")
        time.sleep(policy.get('scanner', {}).get('scan_interval_seconds', 300))
if __name__ == "__main__":
    main_loop()
_

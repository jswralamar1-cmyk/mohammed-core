import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path

# Force unbuffered output so logs appear in Render immediately
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from core.brain.memory import Memory
from core.tools.risk_governor import RiskGovernor
from core.tools.market_scan import MarketScanner
from core.tools.weighted_brain import WeightedBrain
from core.tools.order_router import OrderRouter


def load_policy():
    """Load policy from file, then override API keys from environment variables."""
    policy_path = Path("storage/policy.json")
    if policy_path.exists():
        with open(policy_path, "r") as f:
            policy = json.load(f)
    else:
        policy = {}

    # Override with environment variables if set (for Render deployment)
    api_key = os.environ.get("BINANCE_API_KEY")
    api_secret = os.environ.get("BINANCE_API_SECRET")

    if api_key:
        policy["binance_api_key"] = api_key
    if api_secret:
        policy["binance_api_secret"] = api_secret

    return policy


def main_loop():
    print(f"[{datetime.now()}] MohammedCore Worker started.")

    memory = Memory(data_path=Path("storage/state.json"))
    policy = load_policy()

    print(f"[{datetime.now()}] API Key loaded: {'YES' if policy.get('binance_api_key') else 'NO'}")

    scanner = MarketScanner(policy)
    brain = WeightedBrain(policy)
    governor = RiskGovernor(policy, memory)
    router = OrderRouter(policy, memory)

    while True:
        try:
            print(f"[{datetime.now()}] Scanning market...")
            candidates = scanner.scan_for_candidates()

            if not candidates:
                print(f"[{datetime.now()}] No candidates found. Waiting for next cycle.")
                time.sleep(60)
                continue

            for candidate in candidates:
                symbol = candidate['symbol']
                print(f"[{datetime.now()}] Analyzing candidate: {symbol}")

                from core.tools.momentum_strategy import MomentumStrategy
                from core.tools.pattern_strategy import PatternStrategy

                momentum_strategy = MomentumStrategy()
                pattern_strategy = PatternStrategy()

                scores = [
                    momentum_strategy.analyze(candidate['candles']),
                    pattern_strategy.analyze(candidate['candles'])
                ]

                brain_dump = brain.evaluate(scores)
                signal = governor.validate_trade(symbol, brain_dump, candidate)

                if not signal.approved:
                    print(f"[{datetime.now()}] Trade REJECTED for {symbol}: {signal.reason}")
                    continue

                print(f"[{datetime.now()}] Trade APPROVED for {symbol}. Routing order...")
                result = router.route(signal)

                if result['success']:
                    print(f"[{datetime.now()}] Order PLACED for {symbol}: {result['status']}")
                else:
                    print(f"[{datetime.now()}] Order FAILED for {symbol}: {result['status']}")

            print(f"[{datetime.now()}] Scan cycle complete. Waiting...")
            time.sleep(policy.get('scanner', {}).get('scan_interval_seconds', 300))

        except Exception as e:
            print(f"[{datetime.now()}] ERROR in main loop: {type(e).__name__}: {e}")
            time.sleep(30)


if __name__ == "__main__":
    main_loop()

import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path

# Force unbuffered output so logs appear in Render immediately
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

import requests as _req
try:
    _my_ip = _req.get('https://api.ipify.org', timeout=5).text.strip()
    print(f'[OUTBOUND IP] {_my_ip}', flush=True)
except Exception as _e:
    print(f'[OUTBOUND IP] Could not detect: {_e}', flush=True)

from core.brain.memory import Memory
from core.tools.risk_governor import RiskGovernor
from core.tools.market_scan import MarketScanner
from core.tools.weighted_brain import WeightedBrain
from core.tools.order_router import OrderRouter
from core.tools.trade_monitor import TradeMonitor


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
    print(f"[{datetime.now()}] MohammedCore Worker started.", flush=True)

    memory = Memory(data_path=Path("storage/state.json"))
    policy = load_policy()

    print(f"[{datetime.now()}] API Key loaded: {'YES' if policy.get('binance_api_key') else 'NO'}", flush=True)
    print(f"[{datetime.now()}] Max positions: {policy.get('max_open_positions', 10)}", flush=True)

    scanner = MarketScanner(policy)
    brain = WeightedBrain(policy)
    governor = RiskGovernor(policy, memory)
    router = OrderRouter(policy, memory)
    monitor = TradeMonitor(memory, policy)   # ← وحدة المتابعة

    from core.tools.momentum_strategy import MomentumStrategy
    from core.tools.pattern_strategy import PatternStrategy

    while True:
        try:
            # ═══════════════════════════════════════════
            # الخطوة 1: تابع الصفقات المفتوحة أولاً
            # ═══════════════════════════════════════════
            monitor.check_all_positions()

            # ═══════════════════════════════════════════
            # الخطوة 2: امسح السوق وافتح صفقات جديدة
            # ═══════════════════════════════════════════
            print(f"[{datetime.now()}] Scanning market...", flush=True)
            candidates = scanner.scan_for_candidates()

            if not candidates:
                print(f"[{datetime.now()}] No candidates found. Waiting for next cycle.", flush=True)
                time.sleep(60)
                continue

            momentum_strategy = MomentumStrategy()
            pattern_strategy = PatternStrategy()

            placed = 0
            for candidate in candidates:
                symbol = candidate['symbol']
                print(f"[{datetime.now()}] Analyzing candidate: {symbol}", flush=True)

                scores = [
                    momentum_strategy.analyze(candidate['candles']),
                    pattern_strategy.analyze(candidate['candles'])
                ]

                brain_dump = brain.evaluate(scores)
                signal = governor.validate_trade(symbol, brain_dump, candidate)

                if not signal.approved:
                    print(f"[{datetime.now()}] Trade REJECTED for {symbol}: {signal.reason}", flush=True)
                    continue

                print(f"[{datetime.now()}] Trade APPROVED for {symbol}. Routing order...", flush=True)
                result = router.route(signal)

                if result['success']:
                    placed += 1
                    print(f"[{datetime.now()}] ✅ Order PLACED for {symbol}: {result['status']}", flush=True)
                else:
                    print(f"[{datetime.now()}] ❌ Order FAILED for {symbol}: {result['status']}", flush=True)

            open_count = len(memory.state.get('open_positions', {}))
            print(f"[{datetime.now()}] Scan complete. Placed: {placed} | Open positions: {open_count}", flush=True)
            time.sleep(policy.get('scanner', {}).get('scan_interval_seconds', 300))

        except Exception as e:
            print(f"[{datetime.now()}] ERROR in main loop: {type(e).__name__}: {e}", flush=True)
            time.sleep(30)


if __name__ == "__main__":
    main_loop()

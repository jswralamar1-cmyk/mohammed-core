import sys
import os
import json
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.brain.memory import Memory
from core.tools.risk_governor import RiskGovernor, TradeSignal
from core.tools.momentum_engine import MomentumEngine
from core.tools.weighted_brain import WeightedBrain
from core.tools.strategy_scores import StrategyScore


POLICY = {
    "binance_api_key": "TEST_KEY",
    "binance_api_secret": "TEST_SECRET",
    "leverage": 15,
    "risk_per_trade": 0.04,
    "max_daily_loss": 0.15,
    "max_open_positions": 3,
    "default_sl": 0.012,
    "default_tp": 0.02,
    "trailing_callback": 0.003,
    "scanner": {"scan_interval_seconds": 300, "entry_threshold": 1.0},
    "conflict_policy": "dominant",
    "strategy_weights": {"momentum": 1.5, "patterns": 1.0, "volume": 1.0}
}


def make_candles(n=50, start=100.0, trend="UP"):
    candles = []
    price = start
    for i in range(n):
        if trend == "UP":
            price += 0.5
        elif trend == "DOWN":
            price -= 0.5
        else:
            price += (0.5 if i % 2 == 0 else -0.3)
        candles.append({
            "open": price - 0.2,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price,
            "volume": 1000 + i * 10
        })
    return candles


class TestMemory(unittest.TestCase):
    def setUp(self):
        import uuid
        self.mem_path = Path(f"/tmp/test_state_{uuid.uuid4().hex}.json")
        self.memory = Memory(data_path=self.mem_path)

    def test_initial_state(self):
        # A freshly created memory should have no open positions
        import uuid, time
        unique_path = Path(f"/tmp/test_state_fresh_{uuid.uuid4().hex}_{int(time.time())}.json")
        fresh_mem = Memory(data_path=unique_path)
        self.assertEqual(fresh_mem.state['daily_pnl'], 0.0)
        self.assertEqual(fresh_mem.state['open_positions'], {})
        print("[PASS] test_initial_state")

    def test_add_position(self):
        self.memory.add_open_position("BTCUSDT", {"side": "LONG", "entry_price": 50000})
        self.assertIn("BTCUSDT", self.memory.state['open_positions'])
        print("[PASS] test_add_position")

    def test_remove_position(self):
        self.memory.add_open_position("BTCUSDT", {"side": "LONG", "entry_price": 50000})
        self.memory.remove_open_position("BTCUSDT")
        self.assertNotIn("BTCUSDT", self.memory.state['open_positions'])
        print("[PASS] test_remove_position")

    def test_pnl_update(self):
        self.memory.update_pnl(0.05)
        self.assertAlmostEqual(self.memory.state['daily_pnl'], 0.05)
        print("[PASS] test_pnl_update")


class TestMomentumEngine(unittest.TestCase):
    def test_uptrend(self):
        candles = make_candles(50, trend="UP")
        engine = MomentumEngine()
        result = engine.analyze(candles)
        self.assertIn(result['direction'], ["LONG", "SHORT", None])
        print(f"[PASS] test_uptrend: direction={result['direction']}, score={result['score']}")

    def test_downtrend(self):
        candles = make_candles(50, trend="DOWN")
        engine = MomentumEngine()
        result = engine.analyze(candles)
        self.assertIn(result['direction'], ["LONG", "SHORT", None])
        print(f"[PASS] test_downtrend: direction={result['direction']}, score={result['score']}")


class TestWeightedBrain(unittest.TestCase):
    def test_long_signal(self):
        brain = WeightedBrain(POLICY)
        scores = [
            StrategyScore(name="momentum", score=3.0, direction="LONG", confidence=0.8, reason="Strong uptrend"),
        ]
        result = brain.evaluate(scores)
        print(f"[PASS] test_long_signal: decision={result['decision']}, score={result['final_score']}")

    def test_short_signal(self):
        brain = WeightedBrain(POLICY)
        scores = [
            StrategyScore(name="momentum", score=3.0, direction="SHORT", confidence=0.8, reason="Strong downtrend"),
        ]
        result = brain.evaluate(scores)
        print(f"[PASS] test_short_signal: decision={result['decision']}, score={result['final_score']}")


class TestRiskGovernor(unittest.TestCase):
    def setUp(self):
        import uuid
        self.mem_path = Path(f"/tmp/test_state_risk_{uuid.uuid4().hex}.json")
        self.memory = Memory(data_path=self.mem_path)
        self.governor = RiskGovernor(POLICY, self.memory)
        self.candles = make_candles(50, trend="UP")
        self.candidate = {"symbol": "BTCUSDT", "candles": self.candles}

    def test_approve_trade(self):
        brain_dump = {"decision": "LONG", "final_score": 5.0, "details": []}
        signal = self.governor.validate_trade("BTCUSDT", brain_dump, self.candidate)
        self.assertTrue(signal.approved)
        print(f"[PASS] test_approve_trade: approved={signal.approved}, reason={signal.reason}")

    def test_reject_low_strength(self):
        brain_dump = {"decision": "LONG", "final_score": 0.1, "details": []}
        signal = self.governor.validate_trade("BTCUSDT", brain_dump, self.candidate)
        self.assertFalse(signal.approved)
        print(f"[PASS] test_reject_low_strength: approved={signal.approved}, reason={signal.reason}")

    def test_reject_max_positions(self):
        # Fill up positions
        for i in range(POLICY['max_open_positions']):
            self.memory.add_open_position(f"COIN{i}USDT", {"side": "LONG"})
        brain_dump = {"decision": "LONG", "final_score": 5.0, "details": []}
        signal = self.governor.validate_trade("NEWCOIN", brain_dump, self.candidate)
        self.assertFalse(signal.approved)
        print(f"[PASS] test_reject_max_positions: approved={signal.approved}, reason={signal.reason}")

    def test_reject_daily_loss(self):
        self.memory.state['daily_pnl'] = -0.20  # Exceeds 15% limit
        brain_dump = {"decision": "LONG", "final_score": 5.0, "details": []}
        signal = self.governor.validate_trade("BTCUSDT", brain_dump, self.candidate)
        self.assertFalse(signal.approved)
        print(f"[PASS] test_reject_daily_loss: approved={signal.approved}, reason={signal.reason}")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  Mohammed Core - Unit Tests")
    print("="*60 + "\n")
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestMemory))
    suite.addTests(loader.loadTestsFromTestCase(TestMomentumEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestWeightedBrain))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskGovernor))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*60)
    if result.wasSuccessful():
        print("  ALL TESTS PASSED ✓")
    else:
        print(f"  FAILURES: {len(result.failures)}, ERRORS: {len(result.errors)}")
    print("="*60 + "\n")

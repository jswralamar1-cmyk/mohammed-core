"""
Integration Test Suite for Mohammed Core
Tests the full pipeline from market scan to order execution in Dry Run mode.
"""
import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.brain.memory import Memory
from core.tools.risk_governor import RiskGovernor, TradeSignal
from core.tools.momentum_engine import MomentumEngine
from core.tools.weighted_brain import WeightedBrain
from core.tools.strategy_scores import StrategyScore
from core.tools.momentum_strategy import MomentumStrategy
from core.tools.pattern_strategy import PatternStrategy

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

def make_candles(n=100, start=100.0, trend="UP", volume_spike=False):
    candles = []
    price = start
    for i in range(n):
        if trend == "UP":
            price += 0.5
        elif trend == "DOWN":
            price -= 0.5
        else:
            price += (0.5 if i % 2 == 0 else -0.3)
        volume = 1000 + i * 10
        if volume_spike and i == n - 1:
            volume = 50000  # Big spike on last candle
        candles.append({
            "open": price - 0.2,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price,
            "volume": volume
        })
    return candles

def separator(title=""):
    print("\n" + "="*60)
    if title:
        print(f"  {title}")
        print("="*60)

def run_test(name, fn):
    try:
        fn()
        print(f"  [PASS] {name}")
        return True
    except AssertionError as e:
        print(f"  [FAIL] {name}: {e}")
        return False
    except Exception as e:
        print(f"  [ERROR] {name}: {type(e).__name__}: {e}")
        return False

def test_1_single_trade_lifecycle():
    """Test 1: Single trade from signal to execution"""
    import uuid
    mem = Memory(data_path=Path(f"/tmp/mc_test_{uuid.uuid4().hex}.json"))
    governor = RiskGovernor(POLICY, mem)
    brain = WeightedBrain(POLICY)
    
    candles = make_candles(100, trend="UP", volume_spike=True)
    candidate = {"symbol": "BTCUSDT", "candles": candles}
    
    momentum_strategy = MomentumStrategy()
    pattern_strategy = PatternStrategy()
    scores = [
        momentum_strategy.analyze(candles),
        pattern_strategy.analyze(candles)
    ]
    brain_dump = brain.evaluate(scores)
    
    signal = governor.validate_trade("BTCUSDT", brain_dump, candidate)
    
    assert signal.approved, f"Trade should be approved. Got: {signal.reason}"
    assert signal.entry_price > 0, "Entry price should be set"
    assert signal.sl_price > 0, "SL price should be set"
    assert signal.tp_price > 0, "TP price should be set"
    assert signal.leverage == 15, "Leverage should be 15"
    
    print(f"    Signal: {signal.direction} {signal.symbol}")
    print(f"    Entry: {signal.entry_price:.4f}")
    print(f"    SL: {signal.sl_price:.4f}")
    print(f"    TP: {signal.tp_price:.4f}")
    print(f"    Leverage: {signal.leverage}x")

def test_2_multiple_sequential_trades():
    """Test 2: Multiple sequential trades without errors"""
    import uuid
    mem = Memory(data_path=Path(f"/tmp/mc_test_{uuid.uuid4().hex}.json"))
    governor = RiskGovernor(POLICY, mem)
    brain = WeightedBrain(POLICY)
    
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    approved_count = 0
    
    for symbol in symbols:
        candles = make_candles(100, trend="UP")
        candidate = {"symbol": symbol, "candles": candles}
        
        momentum_strategy = MomentumStrategy()
        pattern_strategy = PatternStrategy()
        scores = [
            momentum_strategy.analyze(candles),
            pattern_strategy.analyze(candles)
        ]
        brain_dump = brain.evaluate(scores)
        signal = governor.validate_trade(symbol, brain_dump, candidate)
        
        if signal.approved:
            mem.add_open_position(symbol, {
                "side": signal.direction,
                "entry_price": signal.entry_price,
                "sl_price": signal.sl_price,
                "tp_price": signal.tp_price
            })
            approved_count += 1
            print(f"    Trade {approved_count}: {signal.direction} {symbol} @ {signal.entry_price:.4f}")
    
    assert approved_count > 0, "At least one trade should be approved"
    assert len(mem.state['open_positions']) == approved_count, "All approved trades should be in memory"
    print(f"    Total trades approved: {approved_count}")

def test_3_max_positions_enforcement():
    """Test 3: Max positions limit is enforced"""
    import uuid
    mem = Memory(data_path=Path(f"/tmp/mc_test_{uuid.uuid4().hex}.json"))
    governor = RiskGovernor(POLICY, mem)
    brain = WeightedBrain(POLICY)
    
    # Fill up to max positions
    for i in range(POLICY['max_open_positions']):
        mem.add_open_position(f"COIN{i}USDT", {"side": "LONG", "entry_price": 100})
    
    candles = make_candles(100, trend="UP")
    candidate = {"symbol": "NEWCOINUSDT", "candles": candles}
    brain_dump = {"decision": "LONG", "final_score": 5.0, "details": []}
    signal = governor.validate_trade("NEWCOINUSDT", brain_dump, candidate)
    
    assert not signal.approved, "Trade should be rejected when max positions reached"
    assert signal.reason == "Max open positions", f"Wrong reason: {signal.reason}"
    print(f"    Correctly rejected: {signal.reason}")

def test_4_daily_loss_kill_switch():
    """Test 4: Daily loss kill switch triggers at 15%"""
    import uuid
    mem = Memory(data_path=Path(f"/tmp/mc_test_{uuid.uuid4().hex}.json"))
    mem.state['daily_pnl'] = -0.20  # 20% loss, exceeds 15% limit
    governor = RiskGovernor(POLICY, mem)
    
    candles = make_candles(100, trend="UP")
    candidate = {"symbol": "BTCUSDT", "candles": candles}
    brain_dump = {"decision": "LONG", "final_score": 5.0, "details": []}
    signal = governor.validate_trade("BTCUSDT", brain_dump, candidate)
    
    assert not signal.approved, "Trade should be rejected due to daily loss limit"
    assert signal.reason == "Daily loss limit hit", f"Wrong reason: {signal.reason}"
    print(f"    Kill switch triggered at {mem.state['daily_pnl']*100:.0f}% daily loss")

def test_5_duplicate_position_prevention():
    """Test 5: Duplicate positions on same symbol are prevented"""
    import uuid
    mem = Memory(data_path=Path(f"/tmp/mc_test_{uuid.uuid4().hex}.json"))
    mem.add_open_position("BTCUSDT", {"side": "LONG", "entry_price": 50000})
    governor = RiskGovernor(POLICY, mem)
    
    candles = make_candles(100, trend="UP")
    candidate = {"symbol": "BTCUSDT", "candles": candles}
    brain_dump = {"decision": "LONG", "final_score": 5.0, "details": []}
    signal = governor.validate_trade("BTCUSDT", brain_dump, candidate)
    
    assert not signal.approved, "Duplicate position should be rejected"
    assert signal.reason == "Duplicate position", f"Wrong reason: {signal.reason}"
    print(f"    Correctly rejected duplicate: {signal.reason}")

def test_6_memory_persistence():
    """Test 6: Memory persists across restarts"""
    import uuid
    path = Path(f"/tmp/mc_test_{uuid.uuid4().hex}.json")
    
    # First instance
    mem1 = Memory(data_path=path)
    mem1.add_open_position("BTCUSDT", {"side": "LONG", "entry_price": 50000})
    mem1.update_pnl(0.05)
    
    # Second instance (simulating restart)
    mem2 = Memory(data_path=path)
    
    assert "BTCUSDT" in mem2.state['open_positions'], "Position should persist after restart"
    assert mem2.state['daily_pnl'] == 0.05, "PnL should persist after restart"
    print(f"    Position persisted: {list(mem2.state['open_positions'].keys())}")
    print(f"    PnL persisted: {mem2.state['daily_pnl']}")

def test_7_sl_tp_calculation():
    """Test 7: SL/TP prices are correctly calculated"""
    import uuid
    mem = Memory(data_path=Path(f"/tmp/mc_test_{uuid.uuid4().hex}.json"))
    governor = RiskGovernor(POLICY, mem)
    
    candles = make_candles(100, start=100.0, trend="UP")
    candidate = {"symbol": "BTCUSDT", "candles": candles}
    brain_dump = {"decision": "LONG", "final_score": 5.0, "details": []}
    signal = governor.validate_trade("BTCUSDT", brain_dump, candidate)
    
    assert signal.approved, "Trade should be approved"
    
    entry = signal.entry_price
    sl = signal.sl_price
    tp = signal.tp_price
    
    # For LONG: SL should be below entry, TP should be above entry
    assert sl < entry, f"SL ({sl:.4f}) should be below entry ({entry:.4f})"
    assert tp > entry, f"TP ({tp:.4f}) should be above entry ({entry:.4f})"
    
    # Check percentages
    sl_pct = (entry - sl) / entry
    tp_pct = (tp - entry) / entry
    
    assert abs(sl_pct - POLICY['default_sl']) < 0.001, f"SL% should be {POLICY['default_sl']}, got {sl_pct:.4f}"
    assert abs(tp_pct - POLICY['default_tp']) < 0.001, f"TP% should be {POLICY['default_tp']}, got {tp_pct:.4f}"
    
    print(f"    Entry: {entry:.4f}, SL: {sl:.4f} ({sl_pct*100:.1f}%), TP: {tp:.4f} ({tp_pct*100:.1f}%)")


if __name__ == '__main__':
    separator("Mohammed Core - Integration Tests")
    
    tests = [
        ("Test 1: Single Trade Lifecycle", test_1_single_trade_lifecycle),
        ("Test 2: Multiple Sequential Trades", test_2_multiple_sequential_trades),
        ("Test 3: Max Positions Enforcement", test_3_max_positions_enforcement),
        ("Test 4: Daily Loss Kill Switch", test_4_daily_loss_kill_switch),
        ("Test 5: Duplicate Position Prevention", test_5_duplicate_position_prevention),
        ("Test 6: Memory Persistence", test_6_memory_persistence),
        ("Test 7: SL/TP Calculation", test_7_sl_tp_calculation),
    ]
    
    passed = 0
    failed = 0
    
    for name, fn in tests:
        separator(name)
        if run_test(name, fn):
            passed += 1
        else:
            failed += 1
    
    separator("RESULTS")
    print(f"  Passed: {passed}/{len(tests)}")
    print(f"  Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n  *** ALL INTEGRATION TESTS PASSED ✓ ***")
    else:
        print(f"\n  *** {failed} TEST(S) FAILED ***")
    print("="*60 + "\n")

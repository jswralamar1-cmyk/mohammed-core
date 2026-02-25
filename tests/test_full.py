"""
اختبار شامل للبوت — يغطي:
1. منع التكرار (duplicate position)
2. متابعة الصفقات (SL/TP)
3. تحديث الذاكرة والـ PnL
4. حساب الكمية والرصيد
5. مزامنة الذاكرة مع بينانس
"""
import sys
import os
import json
import math
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.brain.memory import Memory
from core.tools.execution_guard import ExecutionGuard, TradeSignal
from core.tools.trade_monitor import TradeMonitor
from core.tools.risk_governor import RiskGovernor

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def make_memory(tmp_path=None):
    path = Path(tmp_path or "/tmp/test_state.json")
    if path.exists():
        path.unlink()
    return Memory(data_path=path)

def make_policy():
    return {
        "binance_api_key": "TEST",
        "binance_api_secret": "TEST",
        "leverage": 15,
        "risk_per_trade": 0.04,
        "max_open_positions": 10,
        "max_daily_loss": 0.15,
        "default_sl": 0.012,
        "default_tp": 0.02,
        "scanner": {"entry_threshold": 1.0},
    }

def make_signal(symbol="BTCUSDT", direction="LONG", sl=98800.0, tp=101000.0):
    return TradeSignal(
        symbol=symbol,
        direction=direction,
        leverage=15,
        reason="Test",
        approved=True,
        sl_price=sl,
        tp_price=tp,
        entry_price=100000.0,
    )

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []

def test(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((name, status, detail))
    print(f"  {status} — {name}" + (f" | {detail}" if detail else ""))

# ─────────────────────────────────────────────
# TEST 1: منع التكرار من الذاكرة
# ─────────────────────────────────────────────
print("\n[TEST 1] Duplicate position prevention (memory)")
mem = make_memory("/tmp/t1.json")
policy = make_policy()
mem.add_open_position("BTCUSDT", {"side": "BUY", "quantity": 0.01, "entry_price": 100000})

governor = RiskGovernor(policy, mem)
candles = [{"close": 100000.0}] * 30
candidate = {"candles": candles}
brain_dump = {"decision": "LONG", "final_score": 3.0}

signal = governor.validate_trade("BTCUSDT", brain_dump, candidate)
test("Duplicate rejected by RiskGovernor", not signal.approved and signal.reason == "Duplicate position")

signal2 = governor.validate_trade("ETHUSDT", brain_dump, candidate)
test("New symbol approved", signal2.approved, f"reason={signal2.reason}")

# ─────────────────────────────────────────────
# TEST 2: منع التكرار من بينانس مباشرة
# ─────────────────────────────────────────────
print("\n[TEST 2] Duplicate prevention via Binance positionRisk")
mem2 = make_memory("/tmp/t2.json")
policy2 = make_policy()

guard = ExecutionGuard(policy2, mem2)

# محاكاة بينانس: الرمز عنده position مفتوح
mock_positions = [{"symbol": "SOLUSDT", "positionAmt": "5.0", "entryPrice": "150.0"}]
guard.client._get = MagicMock(side_effect=lambda endpoint, params=None, signed=False: 
    mock_positions if "positionRisk" in endpoint else 
    {"price": "150.0"} if "ticker/price" in endpoint else None
)
guard.client._post = MagicMock(return_value={"orderId": 999, "code": None})

signal = make_signal("SOLUSDT", "LONG", sl=148.0, tp=153.0)
signal.entry_price = 150.0

# يجب أن يرفض لأن بينانس يقول الرمز عنده position
success, status, _ = guard.execute_market(signal)
test("Binance duplicate check blocks order", not success and status == "DUPLICATE_POSITION")
test("Memory synced from Binance", "SOLUSDT" in mem2.state.get("open_positions", {}))

# ─────────────────────────────────────────────
# TEST 3: متابعة الصفقة وإغلاقها عند TP
# ─────────────────────────────────────────────
print("\n[TEST 3] TradeMonitor — Take Profit")
mem3 = make_memory("/tmp/t3.json")
policy3 = make_policy()

mem3.add_open_position("ETHUSDT", {
    "side": "BUY",
    "quantity": 1.0,
    "entry_price": 3000.0,
    "sl_price": 2964.0,
    "tp_price": 3060.0,
    "leverage": 15,
})

monitor = TradeMonitor(mem3, policy3)

# محاكاة: السعر وصل للـ TP (3070 > 3060)
monitor.client._get = MagicMock(side_effect=lambda endpoint, params=None, signed=False:
    [{"symbol": "ETHUSDT", "positionAmt": "1.0"}] if "positionRisk" in endpoint else
    {"price": "3070.0"} if "ticker/price" in endpoint else
    {"symbols": []} if "exchangeInfo" in endpoint else None
)
monitor.client._post = MagicMock(return_value={"orderId": 1001})

monitor.check_all_positions()

test("TP: Position removed from memory", "ETHUSDT" not in mem3.state.get("open_positions", {}))
test("TP: PnL updated (positive)", mem3.state.get("daily_pnl", 0) > 0,
     f"pnl={mem3.state.get('daily_pnl', 0):.2f}")

# ─────────────────────────────────────────────
# TEST 4: متابعة الصفقة وإغلاقها عند SL
# ─────────────────────────────────────────────
print("\n[TEST 4] TradeMonitor — Stop Loss")
mem4 = make_memory("/tmp/t4.json")
policy4 = make_policy()

mem4.add_open_position("BNBUSDT", {
    "side": "BUY",
    "quantity": 2.0,
    "entry_price": 500.0,
    "sl_price": 494.0,
    "tp_price": 510.0,
    "leverage": 15,
})

monitor4 = TradeMonitor(mem4, policy4)

# محاكاة: السعر نزل تحت SL (490 < 494)
monitor4.client._get = MagicMock(side_effect=lambda endpoint, params=None, signed=False:
    [{"symbol": "BNBUSDT", "positionAmt": "2.0"}] if "positionRisk" in endpoint else
    {"price": "490.0"} if "ticker/price" in endpoint else
    {"symbols": []} if "exchangeInfo" in endpoint else None
)
monitor4.client._post = MagicMock(return_value={"orderId": 1002})

monitor4.check_all_positions()

test("SL: Position removed from memory", "BNBUSDT" not in mem4.state.get("open_positions", {}))
test("SL: PnL updated (negative)", mem4.state.get("daily_pnl", 0) < 0,
     f"pnl={mem4.state.get('daily_pnl', 0):.2f}")

# ─────────────────────────────────────────────
# TEST 5: صفقة مغلقة من بينانس (خارجياً)
# ─────────────────────────────────────────────
print("\n[TEST 5] TradeMonitor — Position closed externally on Binance")
mem5 = make_memory("/tmp/t5.json")
policy5 = make_policy()

mem5.add_open_position("ADAUSDT", {
    "side": "SELL",
    "quantity": 100.0,
    "entry_price": 1.0,
    "sl_price": 1.012,
    "tp_price": 0.98,
    "leverage": 15,
})

monitor5 = TradeMonitor(mem5, policy5)

# محاكاة: بينانس يقول positionAmt = 0 (مغلقة)
monitor5.client._get = MagicMock(side_effect=lambda endpoint, params=None, signed=False:
    [{"symbol": "ADAUSDT", "positionAmt": "0.0"}] if "positionRisk" in endpoint else
    {"price": "0.99"} if "ticker/price" in endpoint else None
)

monitor5.check_all_positions()
test("Externally closed: removed from memory", "ADAUSDT" not in mem5.state.get("open_positions", {}))

# ─────────────────────────────────────────────
# TEST 6: حد الحد الأقصى للصفقات = 10
# ─────────────────────────────────────────────
print("\n[TEST 6] Max open positions = 10")
mem6 = make_memory("/tmp/t6.json")
policy6 = make_policy()
governor6 = RiskGovernor(policy6, mem6)

# أضف 10 صفقات
for i in range(10):
    mem6.add_open_position(f"COIN{i}USDT", {"side": "BUY", "quantity": 1.0, "entry_price": 100.0})

candles = [{"close": 100.0}] * 30
brain_dump = {"decision": "LONG", "final_score": 5.0}
signal = governor6.validate_trade("NEWCOIN USDT", brain_dump, {"candles": candles})
test("Max 10 positions enforced", not signal.approved and signal.reason == "Max open positions",
     f"positions={len(mem6.state.get('open_positions', {}))}")

# أضف أقل من 10 — يجب أن يُقبل
mem7 = make_memory("/tmp/t7.json")
governor7 = RiskGovernor(policy6, mem7)
for i in range(9):
    mem7.add_open_position(f"COIN{i}USDT", {"side": "BUY", "quantity": 1.0, "entry_price": 100.0})
signal7 = governor7.validate_trade("NEWCOINUSDT", brain_dump, {"candles": candles})
test("9 positions: new trade allowed", signal7.approved, f"reason={signal7.reason}")

# ─────────────────────────────────────────────
# TEST 7: حساب الكمية صحيح
# ─────────────────────────────────────────────
print("\n[TEST 7] Quantity calculation")
mem8 = make_memory("/tmp/t8.json")
policy8 = make_policy()
guard8 = ExecutionGuard(policy8, mem8)

# avail = $30, leverage = 15, sl_pct = 1.2%
# max_notional = 30 * 15 * 0.85 = 382.5
# risk_amount = 30 * 0.04 = 1.2
# notional = 1.2 / 0.012 = 100 → min(100, 382.5) = 100
# quantity = 100 / 100 = 1.0

guard8.client._get = MagicMock(return_value={"symbols": [
    {"symbol": "TESTUSDT", "filters": [
        {"filterType": "LOT_SIZE", "stepSize": "0.1"}
    ]}
]})

qty = guard8._get_quantity("TESTUSDT", 100.0, 0.012, 30.0)
test("Quantity calculated correctly", qty == 1.0, f"qty={qty}")

# ─────────────────────────────────────────────
# النتائج النهائية
# ─────────────────────────────────────────────
print("\n" + "="*50)
passed = sum(1 for _, s, _ in results if s == PASS)
failed = sum(1 for _, s, _ in results if s == FAIL)
total = len(results)
print(f"RESULTS: {passed}/{total} passed, {failed} failed")
if failed > 0:
    print("\nFailed tests:")
    for name, status, detail in results:
        if status == FAIL:
            print(f"  ❌ {name} | {detail}")
    sys.exit(1)
else:
    print("🎉 All tests passed!")
    sys.exit(0)

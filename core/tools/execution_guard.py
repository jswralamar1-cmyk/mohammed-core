from dataclasses import dataclass
from typing import Optional
from core.brain.policy import LIVE_TRADING
from core.tools.binance_futures import BinanceFutures
from core.tools.position_sizer import PositionSizer
from core.tools.sl_tp_manager import SLTPManager
from core.tools.trade_logger import TradeLogger
from core.tools.risk_governor import RiskGovernor
from core.brain.memory import Memory
@dataclass
class TradeSignal:
    symbol: str
    direction: str  # LONG | SHORT
    leverage: int
    reason: str
    brain_dump: Optional[dict] = None
    risk_override: Optional[float] = None
class ExecutionGuard:
    def __init__(self, policy: dict, memory: Memory):
        self.policy = policy
        self.memory = memory
        self.client = BinanceFutures(policy.get('binance_api_key'), policy.get('binance_api_secret'))
        self.sizer = PositionSizer(policy)
        self.sltp = SLTPManager()
        self.logger = TradeLogger()
        self.governor = RiskGovernor(policy, memory)
    def execute_market(self, signal: TradeSignal):
        

        if not LIVE_TRADING:
            print(f"--- [DRY RUN] ---")
            print(f"Signal: {signal.direction} {signal.symbol}")
            print(f"Leverage: {signal.leverage}")
            print(f"Reason: {signal.reason}")
            print(f"--------------------")
            return True, "DRY_RUN_SUCCESS", {"symbol": signal.symbol, "dry_run": True}
        side = "BUY" if signal.direction == "LONG" else "SELL"
        # 1. Set leverage
        self.client._post("/fapi/v1/leverage", {"symbol": signal.symbol, "leverage": signal.leverage}, signed=True)
        # Set margin type — ignore error if already set
        try:
            self.client._post("/fapi/v1/marginType", {"symbol": signal.symbol, "marginType": "ISOLATED"}, signed=True)
        except Exception:
            pass
        # 2. Get current price and calculate quantity
        ticker = self.client._get("/fapi/v1/ticker/price", {"symbol": signal.symbol})
        if not ticker:
            return False, "PRICE_FETCH_FAILED", None
        entry_price = float(ticker['price'])
        sl_pct = abs(entry_price - signal.sl_price) / entry_price if signal.sl_price > 0 else 0.012
        quantity = self.sizer.calculate_quantity(signal.symbol, entry_price, sl_pct, signal.risk_override)
        if quantity == 0:
            return False, "ZERO_QUANTITY", None
        # 3. Place market order
        order = self.client._post(
            "/fapi/v1/order",
            {
                "symbol": signal.symbol,
                "side": side,
                "type": "MARKET",
                "quantity": quantity,
            },
            signed=True
        )
        if not order:
            return False, "ORDER_FAILED", None
        # 4. Record and Log
        self.memory.add_open_position(signal.symbol, order)
        self.logger.log_entry(signal, order, quantity)
        return True, "SUCCESS", order

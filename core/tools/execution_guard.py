import math
from dataclasses import dataclass, field
from typing import Optional
from core.brain.policy import LIVE_TRADING
from core.tools.binance_futures import BinanceFutures
from core.tools.trade_logger import TradeLogger
from core.brain.memory import Memory


@dataclass
class TradeSignal:
    symbol: str
    direction: str        # LONG | SHORT
    leverage: int
    reason: str
    approved: bool = False
    strength: float = 0.0
    sl_price: float = 0.0
    tp_price: float = 0.0
    entry_price: float = 0.0
    risk_override: Optional[float] = None
    brain_dump: Optional[dict] = field(default_factory=dict)


class ExecutionGuard:
    def __init__(self, policy: dict, memory: Memory):
        self.policy = policy
        self.memory = memory
        self.client = BinanceFutures(
            policy.get('binance_api_key'),
            policy.get('binance_api_secret')
        )
        self.logger = TradeLogger()

    def _get_balance(self) -> float:
        """Fetch available USDT balance from Binance Futures account."""
        try:
            account = self.client._get("/fapi/v2/account", signed=True)
            if not account:
                print("[ExecutionGuard] Account fetch returned None", flush=True)
                return 100.0
            # Try assets list first
            for asset in account.get('assets', []):
                if asset.get('asset') == 'USDT':
                    avail = float(asset.get('availableBalance', 0))
                    wallet = float(asset.get('walletBalance', 0))
                    bal = avail if avail > 0 else wallet
                    print(f"[ExecutionGuard] USDT avail={avail} wallet={wallet} using={bal}", flush=True)
                    return bal if bal > 0 else 100.0
            # Fallback to top-level
            total = float(account.get('totalWalletBalance', 0))
            avail = float(account.get('availableBalance', 0))
            bal = avail if avail > 0 else total
            print(f"[ExecutionGuard] Fallback balance: total={total} avail={avail} using={bal}", flush=True)
            return bal if bal > 0 else 100.0
        except Exception as e:
            print(f"[ExecutionGuard] Balance fetch error: {e}", flush=True)
            return 100.0

    def _get_quantity(self, symbol: str, entry_price: float, sl_pct: float, risk_override: float = None) -> float:
        """Calculate order quantity based on risk parameters."""
        try:
            balance = self._get_balance()
            print(f"[ExecutionGuard] Balance: ${balance:.2f}", flush=True)

            risk_pct = risk_override if risk_override else self.policy.get('risk_per_trade', 0.02)
            leverage = self.policy.get('leverage', 10)
            if sl_pct <= 0:
                sl_pct = 0.012

            risk_amount = balance * risk_pct
            notional = (risk_amount / sl_pct) * leverage
            quantity = notional / entry_price

            # Get lot size precision
            exchange_info = self.client._get("/fapi/v1/exchangeInfo")
            if exchange_info:
                for s in exchange_info.get('symbols', []):
                    if s['symbol'] == symbol:
                        for f in s.get('filters', []):
                            if f['filterType'] == 'LOT_SIZE':
                                step = float(f['stepSize'])
                                quantity = math.floor(quantity / step) * step
                                decimals = len(str(step).rstrip('0').split('.')[-1]) if '.' in str(step) else 0
                                quantity = round(quantity, decimals)
                                break
                        break

            print(f"[ExecutionGuard] Quantity: {quantity} {symbol} (notional: ${notional:.2f})", flush=True)
            return quantity
        except Exception as e:
            print(f"[ExecutionGuard] Quantity calc error: {e}", flush=True)
            return 0.0

    def execute_market(self, signal: TradeSignal):
        if not LIVE_TRADING:
            print(f"--- [DRY RUN] ---", flush=True)
            print(f"Signal: {signal.direction} {signal.symbol}", flush=True)
            print(f"Leverage: {signal.leverage}", flush=True)
            print(f"Reason: {signal.reason}", flush=True)
            print(f"--------------------", flush=True)
            return True, "DRY_RUN_SUCCESS", {"symbol": signal.symbol, "dry_run": True}

        side = "BUY" if signal.direction == "LONG" else "SELL"

        # 1. Set leverage
        lev_result = self.client._post("/fapi/v1/leverage", {
            "symbol": signal.symbol,
            "leverage": signal.leverage
        }, signed=True)
        print(f"[ExecutionGuard] Leverage set: {lev_result}", flush=True)

        # 2. Set margin type to CROSS (compatible with Multi-Assets Mode)
        # Skip if already set (-4046) or Multi-Assets mode active (-4168)
        margin_result = self.client._post("/fapi/v1/marginType", {
            "symbol": signal.symbol,
            "marginType": "CROSSED"
        }, signed=True)
        if margin_result and margin_result.get('code') not in [None, -4046, -4168]:
            print(f"[ExecutionGuard] MarginType: {margin_result}", flush=True)

        # 3. Get current price
        ticker = self.client._get("/fapi/v1/ticker/price", {"symbol": signal.symbol})
        if not ticker:
            return False, "PRICE_FETCH_FAILED", None
        entry_price = float(ticker['price'])

        # 4. Calculate SL percentage and quantity
        if signal.sl_price > 0 and entry_price > 0:
            sl_pct = abs(entry_price - signal.sl_price) / entry_price
        else:
            sl_pct = 0.012  # default 1.2%

        quantity = self._get_quantity(signal.symbol, entry_price, sl_pct, signal.risk_override)
        if quantity <= 0:
            return False, "ZERO_QUANTITY", None

        # 5. Place market order
        order = self.client._post("/fapi/v1/order", {
            "symbol": signal.symbol,
            "side": side,
            "type": "MARKET",
            "quantity": quantity,
        }, signed=True)

        if not order or order.get('code'):
            print(f"[ExecutionGuard] Order failed: {order}", flush=True)
            return False, "ORDER_FAILED", order

        print(f"[ExecutionGuard] Order placed: {order.get('orderId')} {side} {quantity} {signal.symbol} @ ~{entry_price}", flush=True)

        # 6. Record in memory and log
        self.memory.add_open_position(signal.symbol, {
            "orderId": order.get('orderId'),
            "side": side,
            "quantity": quantity,
            "entry_price": entry_price,
            "sl_price": signal.sl_price,
            "tp_price": signal.tp_price,
            "leverage": signal.leverage,
        })
        self.logger.log_entry(signal, order, quantity)

        return True, "SUCCESS", order

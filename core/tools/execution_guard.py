import math
from dataclasses import dataclass, field
from typing import Optional
from core.brain.policy import LIVE_TRADING
from core.tools.binance_futures import BinanceFutures
from core.tools.trade_logger import TradeLogger
from core.brain.memory import Memory

# Minimum available balance required to open a new position (USDT)
MIN_AVAILABLE_BALANCE = 5.0


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

    def _get_account_balances(self) -> tuple:
        """
        Returns (avail_balance, wallet_balance) from Binance Futures account.
        avail_balance = free margin available for new positions.
        wallet_balance = total equity (including unrealized PnL).
        """
        try:
            account = self.client._get("/fapi/v2/account", signed=True)
            if not account:
                print("[ExecutionGuard] Account fetch returned None", flush=True)
                return 0.0, 0.0

            avail_balance = 0.0
            wallet_balance = 0.0

            # Try assets list first
            for asset in account.get('assets', []):
                if asset.get('asset') == 'USDT':
                    avail_balance = float(asset.get('availableBalance', 0))
                    wallet_balance = float(asset.get('walletBalance', 0))
                    break

            # Fallback to top-level fields
            if wallet_balance == 0:
                wallet_balance = float(account.get('totalWalletBalance', 0))
                avail_balance = float(account.get('availableBalance', 0))

            print(f"[ExecutionGuard] USDT avail={avail_balance:.4f} wallet={wallet_balance:.4f}", flush=True)
            return avail_balance, wallet_balance

        except Exception as e:
            print(f"[ExecutionGuard] Balance fetch error: {e}", flush=True)
            return 0.0, 0.0

    def _get_quantity(self, symbol: str, entry_price: float, sl_pct: float,
                      avail_balance: float, risk_override: float = None) -> float:
        """
        Calculate order quantity using available balance.
        The notional is capped at avail_balance * leverage * 0.85 (15% safety buffer).
        """
        try:
            risk_pct = risk_override if risk_override else self.policy.get('risk_per_trade', 0.02)
            leverage = self.policy.get('leverage', 10)
            if sl_pct <= 0:
                sl_pct = 0.012

            # Hard cap: never exceed 85% of available margin * leverage
            max_notional = avail_balance * leverage * 0.85

            # Risk-based notional: risk_amount / sl_pct gives position size
            risk_amount = avail_balance * risk_pct
            notional = (risk_amount / sl_pct)  # no leverage multiplication here — margin-based

            # Cap at max notional
            notional = min(notional, max_notional)
            quantity = notional / entry_price

            # Get lot size precision from exchange info
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

            print(f"[ExecutionGuard] Quantity: {quantity} {symbol} (notional: ${notional:.2f}, avail: ${avail_balance:.2f})", flush=True)
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

        # 0a. تحقق من بينانس مباشرة — لا تفتح صفقة إذا الرمز عنده position مفتوح فعلياً
        try:
            positions = self.client._get("/fapi/v2/positionRisk", {"symbol": signal.symbol}, signed=True)
            if positions:
                for p in positions:
                    if p.get('symbol') == signal.symbol and abs(float(p.get('positionAmt', 0))) > 0:
                        print(f"[ExecutionGuard] SKIP {signal.symbol}: Already has open position on Binance (amt={p.get('positionAmt')})", flush=True)
                        # تأكد إن الذاكرة تعرف عن هذه الصفقة
                        if signal.symbol not in self.memory.state.get('open_positions', {}):
                            self.memory.add_open_position(signal.symbol, {
                                'side': 'BUY' if float(p.get('positionAmt', 0)) > 0 else 'SELL',
                                'quantity': abs(float(p.get('positionAmt', 0))),
                                'entry_price': float(p.get('entryPrice', 0)),
                                'sl_price': signal.sl_price,
                                'tp_price': signal.tp_price,
                                'leverage': signal.leverage,
                            })
                            print(f"[ExecutionGuard] Synced {signal.symbol} to memory from Binance.", flush=True)
                        return False, "DUPLICATE_POSITION", None
        except Exception as e:
            print(f"[ExecutionGuard] positionRisk check error (non-fatal): {e}", flush=True)

        # 0b. Check available balance FIRST — skip if insufficient
        avail_balance, wallet_balance = self._get_account_balances()
        if avail_balance < MIN_AVAILABLE_BALANCE:
            print(f"[ExecutionGuard] Skipping {signal.symbol}: avail=${avail_balance:.2f} < min=${MIN_AVAILABLE_BALANCE}", flush=True)
            return False, "INSUFFICIENT_BALANCE", None

        # 1. Set leverage (with fallback to lower leverage if symbol doesn't support 15x)
        lev_result = self.client._post("/fapi/v1/leverage", {
            "symbol": signal.symbol,
            "leverage": signal.leverage
        }, signed=True)

        # Handle leverage not valid for this symbol
        if lev_result and lev_result.get('code') == -4028:
            print(f"[ExecutionGuard] Leverage {signal.leverage}x not supported for {signal.symbol}, trying 10x", flush=True)
            lev_result = self.client._post("/fapi/v1/leverage", {
                "symbol": signal.symbol,
                "leverage": 10
            }, signed=True)
            if lev_result and lev_result.get('code'):
                print(f"[ExecutionGuard] Cannot set leverage for {signal.symbol}: {lev_result}", flush=True)
                return False, "LEVERAGE_FAILED", None
            signal.leverage = 10

        print(f"[ExecutionGuard] Leverage set: {lev_result}", flush=True)

        # 2. Set margin type to CROSS — ignore -4046 (already set) and -4168 (multi-assets mode)
        self.client._post("/fapi/v1/marginType", {
            "symbol": signal.symbol,
            "marginType": "CROSSED"
        }, signed=True)

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

        quantity = self._get_quantity(signal.symbol, entry_price, sl_pct, avail_balance, signal.risk_override)
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
            err_code = order.get('code') if order else 'None'
            err_msg = order.get('msg', '') if order else ''
            print(f"[ExecutionGuard] Order failed [{err_code}]: {err_msg}", flush=True)
            return False, "ORDER_FAILED", order

        print(f"[ExecutionGuard] ✅ Order placed: #{order.get('orderId')} {side} {quantity} {signal.symbol} @ ~{entry_price:.4f}", flush=True)

        # 6. Record in memory
        self.memory.add_open_position(signal.symbol, {
            "orderId": order.get('orderId'),
            "side": side,
            "quantity": quantity,
            "entry_price": entry_price,
            "sl_price": signal.sl_price,
            "tp_price": signal.tp_price,
            "leverage": signal.leverage,
        })

        # 7. Log trade entry
        try:
            self.logger.log_trade(
                symbol=signal.symbol,
                side=side,
                entry_price=entry_price,
                exit_price=None,
                pnl=None,
                duration=None,
                reason=signal.reason
            )
        except Exception as log_err:
            print(f"[ExecutionGuard] Logging error (non-fatal): {log_err}", flush=True)

        return True, "SUCCESS", order

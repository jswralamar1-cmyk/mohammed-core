"""
TradeMonitor — يراقب الصفقات المفتوحة في كل دورة ويغلقها عند SL أو TP.
يُستدعى من runner.py في بداية كل دورة مسح.
"""
import math
from datetime import datetime
from core.brain.memory import Memory
from core.tools.binance_futures import BinanceFutures
from core.tools.trade_logger import TradeLogger


class TradeMonitor:
    def __init__(self, memory: Memory, policy: dict):
        self.memory = memory
        self.policy = policy
        self.client = BinanceFutures(
            policy.get('binance_api_key'),
            policy.get('binance_api_secret')
        )
        self.logger = TradeLogger()

    def check_all_positions(self):
        """
        يمر على كل الصفقات المفتوحة في الذاكرة ويتحقق من:
        1. هل الصفقة لا تزال مفتوحة في بينانس؟
        2. هل وصل السعر لـ TP أو SL؟
        3. هل تجاوز الخسارة الحد الأقصى؟
        """
        open_positions = dict(self.memory.state.get('open_positions', {}))
        if not open_positions:
            return

        print(f"[TradeMonitor] Checking {len(open_positions)} open position(s)...", flush=True)

        for symbol, pos in open_positions.items():
            try:
                self._check_position(symbol, pos)
            except Exception as e:
                print(f"[TradeMonitor] Error checking {symbol}: {e}", flush=True)

    def _check_position(self, symbol: str, pos: dict):
        """يتحقق من صفقة واحدة ويغلقها إذا لزم."""
        side = pos.get('side', 'BUY')
        entry_price = float(pos.get('entry_price', 0))
        sl_price = float(pos.get('sl_price', 0))
        tp_price = float(pos.get('tp_price', 0))
        quantity = float(pos.get('quantity', 0))
        leverage = int(pos.get('leverage', 15))

        # 1. تحقق من أن الصفقة لا تزال مفتوحة في بينانس
        binance_position = self._get_binance_position(symbol)

        if binance_position is None:
            # فشل في جلب البيانات — تخطى هذه الدورة
            return

        if binance_position == 0:
            # الصفقة أُغلقت من بينانس (SL/TP أو يدوياً)
            print(f"[TradeMonitor] {symbol}: Position already closed on Binance. Cleaning up.", flush=True)
            self._finalize_closed_position(symbol, pos, entry_price, side, quantity, leverage, "CLOSED_EXTERNALLY")
            return

        # 2. جلب السعر الحالي
        ticker = self.client._get("/fapi/v1/ticker/price", {"symbol": symbol})
        if not ticker:
            print(f"[TradeMonitor] {symbol}: Cannot fetch price, skipping.", flush=True)
            return

        current_price = float(ticker['price'])
        direction = "LONG" if side == "BUY" else "SHORT"

        # حساب PnL الحالي
        if direction == "LONG":
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price

        pnl_usdt = pnl_pct * entry_price * quantity * leverage
        print(f"[TradeMonitor] {symbol} {direction} | Entry: {entry_price:.4f} | Now: {current_price:.4f} | PnL: ${pnl_usdt:.2f} ({pnl_pct*100:.2f}%)", flush=True)

        # 3. تحقق من SL
        if sl_price > 0:
            sl_hit = (direction == "LONG" and current_price <= sl_price) or \
                     (direction == "SHORT" and current_price >= sl_price)
            if sl_hit:
                print(f"[TradeMonitor] {symbol}: ❌ STOP LOSS hit! Closing...", flush=True)
                self._close_position(symbol, pos, current_price, "STOP_LOSS")
                return

        # 4. تحقق من TP
        if tp_price > 0:
            tp_hit = (direction == "LONG" and current_price >= tp_price) or \
                     (direction == "SHORT" and current_price <= tp_price)
            if tp_hit:
                print(f"[TradeMonitor] {symbol}: ✅ TAKE PROFIT hit! Closing...", flush=True)
                self._close_position(symbol, pos, current_price, "TAKE_PROFIT")
                return

    def _get_binance_position(self, symbol: str):
        """
        يجلب حجم الـ position الحالي من بينانس.
        يرجع: float (حجم الـ position)، أو None إذا فشل الطلب.
        """
        try:
            positions = self.client._get("/fapi/v2/positionRisk", {"symbol": symbol}, signed=True)
            if not positions:
                return None
            for p in positions:
                if p.get('symbol') == symbol:
                    amt = float(p.get('positionAmt', 0))
                    return abs(amt)
            return 0.0
        except Exception as e:
            print(f"[TradeMonitor] positionRisk error for {symbol}: {e}", flush=True)
            return None

    def _close_position(self, symbol: str, pos: dict, exit_price: float, reason: str):
        """يغلق الصفقة في بينانس ويحدّث الذاكرة."""
        side = pos.get('side', 'BUY')
        quantity = float(pos.get('quantity', 0))
        entry_price = float(pos.get('entry_price', 0))
        leverage = int(pos.get('leverage', 15))
        direction = "LONG" if side == "BUY" else "SHORT"

        # جانب الإغلاق معاكس لجانب الفتح
        close_side = "SELL" if side == "BUY" else "BUY"

        # تقريب الكمية
        quantity = self._round_quantity(symbol, quantity)

        order = self.client._post("/fapi/v1/order", {
            "symbol": symbol,
            "side": close_side,
            "type": "MARKET",
            "quantity": quantity,
            "reduceOnly": "true",
        }, signed=True)

        if order and not order.get('code'):
            print(f"[TradeMonitor] {symbol}: Closed #{order.get('orderId')} | Reason: {reason}", flush=True)
        else:
            err = order.get('msg', '') if order else 'No response'
            print(f"[TradeMonitor] {symbol}: Close order failed: {err}", flush=True)

        # حساب PnL
        if direction == "LONG":
            pnl = (exit_price - entry_price) * quantity
        else:
            pnl = (entry_price - exit_price) * quantity

        self._finalize_closed_position(symbol, pos, exit_price, side, quantity, leverage, reason, pnl)

    def _finalize_closed_position(self, symbol, pos, exit_price, side, quantity, leverage, reason, pnl=None):
        """يحذف الصفقة من الذاكرة ويسجلها."""
        entry_price = float(pos.get('entry_price', 0))
        direction = "LONG" if side == "BUY" else "SHORT"

        if pnl is None:
            if direction == "LONG":
                pnl = (exit_price - entry_price) * quantity
            else:
                pnl = (entry_price - exit_price) * quantity

        # تحديث PnL اليومي
        self.memory.update_pnl(pnl)

        # تسجيل الصفقة في السجل
        try:
            self.logger.log_trade(
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl=round(pnl, 4),
                duration=None,
                reason=reason
            )
        except Exception as e:
            print(f"[TradeMonitor] Log error (non-fatal): {e}", flush=True)

        # حذف من الذاكرة
        self.memory.remove_open_position(symbol)

        emoji = "✅" if pnl >= 0 else "❌"
        print(f"[TradeMonitor] {emoji} {symbol} CLOSED | PnL: ${pnl:.2f} | Reason: {reason}", flush=True)

    def _round_quantity(self, symbol: str, quantity: float) -> float:
        """يقرّب الكمية لأقرب step size مسموح."""
        try:
            info = self.client._get("/fapi/v1/exchangeInfo")
            if info:
                for s in info.get('symbols', []):
                    if s['symbol'] == symbol:
                        for f in s.get('filters', []):
                            if f['filterType'] == 'LOT_SIZE':
                                step = float(f['stepSize'])
                                quantity = math.floor(quantity / step) * step
                                decimals = len(str(step).rstrip('0').split('.')[-1]) if '.' in str(step) else 0
                                return round(quantity, decimals)
        except Exception:
            pass
        return round(quantity, 3)

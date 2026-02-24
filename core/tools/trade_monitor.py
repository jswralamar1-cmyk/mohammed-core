import time
from datetime import datetime
from core.brain.memory import Memory
from core.tools.binance_futures import BinanceFutures
from core.tools.trade_logger import TradeLogger
class TradeMonitor:
    def __init__(self, memory: Memory, policy: dict):
        self.memory = memory
        self.policy = policy
        self.client = BinanceFutures(self.policy['binance_api_key'], self.policy['binance_api_secret'])
        self.logger = TradeLogger()
    def watch(self, trade: dict):
        symbol = trade['symbol']
        entry_price = trade['entry_price']
        sl_price = trade['sl_price']
        tp_price = trade['tp_price']
        position_side = trade['side']
        print(f"[{datetime.now()}] MONITORING: {symbol} {position_side}")
        while True:
            # Check every 10 seconds
            time.sleep(10)
            # Get current price
            ticker = self.client.get_ticker(symbol)
            if not ticker:
                continue
            
            current_price = ticker['price']
            # Check SL/TP
            if position_side == "LONG":
                if current_price <= sl_price:
                    self.close_trade(trade, "STOP_LOSS")
                    break
                if current_price >= tp_price:
                    self.close_trade(trade, "TAKE_PROFIT")
                    break
            
            elif position_side == "SHORT":
                if current_price >= sl_price:
                    self.close_trade(trade, "STOP_LOSS")
                    break
                if current_price <= tp_price:
                    self.close_trade(trade, "TAKE_PROFIT")
                    break
    def close_trade(self, trade: dict, exit_reason: str):
        symbol = trade['symbol']
        side = trade['side']
        quantity = trade['quantity']
        # Close position
        close_side = "SELL" if side == "LONG" else "BUY"
        order = self.client.place_market_order(symbol, close_side, quantity)
        if order:
            exit_price = self.client.get_avg_price(symbol)
            pnl = (exit_price - trade['entry_price']) * quantity if side == "LONG" else (trade['entry_price'] - exit_price) * quantity
            
            # Log trade
            self.logger.log_trade(
                symbol=symbol,
                side=side,
                entry_price=trade['entry_price'],
                exit_price=exit_price,
                pnl=pnl,
                duration=(datetime.now() - trade['entry_time']).total_seconds(),
                reason=exit_reason
            )
            # Remove from memory
            self.memory.remove_position(symbol)
            self.memory.save()
            print(f"[{datetime.now()}] CLOSED: {symbol} at {exit_price} ({exit_reason}) PnL: {pnl}")
_

from dataclasses import dataclass
from typing import Optional

from core.brain.memory import Memory


@dataclass
class TradeSignal:
    symbol: str
    direction: str
    strength: float
    sl_price: float
    tp_price: float
    entry_price: float
    leverage: int
    approved: bool = False
    reason: Optional[str] = None


class RiskGovernor:

    def __init__(self, policy: dict, memory: Memory):
        self.policy = policy
        self.memory = memory

    def validate_trade(self, symbol: str, brain_dump: dict, candidate: dict) -> TradeSignal:
        direction = brain_dump.get('decision')
        strength = brain_dump.get('final_score')

        # 1. Basic signal check
        if not direction or strength < self.policy['scanner']['entry_threshold']:
            return TradeSignal(symbol=symbol, direction=None, strength=strength, sl_price=0, tp_price=0, entry_price=0, leverage=0, approved=False, reason="Low strength")

        # 2. Daily loss limit
        if self.memory.state['daily_pnl'] <= -self.policy['max_daily_loss']:
            return TradeSignal(symbol=symbol, direction=direction, strength=strength, sl_price=0, tp_price=0, entry_price=0, leverage=0, approved=False, reason="Daily loss limit hit")

        # 3. Max open positions
        if len(self.memory.state['open_positions']) >= self.policy['max_open_positions']:
            return TradeSignal(symbol=symbol, direction=direction, strength=strength, sl_price=0, tp_price=0, entry_price=0, leverage=0, approved=False, reason="Max open positions")

        # 4. Duplicate position
        if symbol in self.memory.state['open_positions']:
            return TradeSignal(symbol=symbol, direction=direction, strength=strength, sl_price=0, tp_price=0, entry_price=0, leverage=0, approved=False, reason="Duplicate position")

        # Calculate SL/TP
        sl_pct = self.policy['default_sl']
        tp_pct = self.policy['default_tp']
        last_price = candidate['candles'][-1]['close']

        if direction == "LONG":
            sl_price = last_price * (1 - sl_pct)
            tp_price = last_price * (1 + tp_pct)
        else: # SHORT
            sl_price = last_price * (1 + sl_pct)
            tp_price = last_price * (1 - tp_pct)

        return TradeSignal(
            symbol=symbol,
            direction=direction,
            strength=strength,
            sl_price=sl_price,
            tp_price=tp_price,
            entry_price=last_price, # Assuming market order fills at last price
            leverage=self.policy.get('leverage', 1),
            approved=True,
            reason="All checks passed"
        )

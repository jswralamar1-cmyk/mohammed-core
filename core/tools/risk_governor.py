from core.brain.memory import Memory
from core.tools.execution_guard import TradeSignal


class RiskGovernor:

    def __init__(self, policy: dict, memory: Memory):
        self.policy = policy
        self.memory = memory

    def validate_trade(self, symbol: str, brain_dump: dict, candidate: dict) -> TradeSignal:
        direction = brain_dump.get('decision')
        strength = brain_dump.get('final_score', 0)

        def rejected(reason):
            return TradeSignal(
                symbol=symbol,
                direction=direction or "NONE",
                leverage=0,
                reason=reason,
                approved=False,
                strength=strength,
            )

        # 1. Basic signal check
        entry_threshold = self.policy.get('scanner', {}).get('entry_threshold', 2)
        if not direction or strength < entry_threshold:
            return rejected("Low strength")

        # 2. Daily loss limit
        max_daily_loss = self.policy.get('max_daily_loss', 0.15)
        if self.memory.state.get('daily_pnl', 0) <= -max_daily_loss:
            return rejected("Daily loss limit hit")

        # 3. Max open positions
        max_positions = self.policy.get('max_open_positions', 5)
        if len(self.memory.state.get('open_positions', {})) >= max_positions:
            return rejected("Max open positions")

        # 4. Duplicate position
        if symbol in self.memory.state.get('open_positions', {}):
            return rejected("Duplicate position")

        # Calculate SL/TP
        sl_pct = self.policy.get('default_sl', 0.012)
        tp_pct = self.policy.get('default_tp', 0.02)
        last_price = candidate['candles'][-1]['close']

        if direction == "LONG":
            sl_price = last_price * (1 - sl_pct)
            tp_price = last_price * (1 + tp_pct)
        else:  # SHORT
            sl_price = last_price * (1 + sl_pct)
            tp_price = last_price * (1 - tp_pct)

        return TradeSignal(
            symbol=symbol,
            direction=direction,
            leverage=self.policy.get('leverage', 10),
            reason="All checks passed",
            approved=True,
            strength=strength,
            sl_price=sl_price,
            tp_price=tp_price,
            entry_price=last_price,
            brain_dump=brain_dump,
        )

from typing import List, Dict
from core.tools.strategy_scores import StrategyScore
from core.tools.indicators import Indicators
class RSIStrategy:
    def __init__(self, period: int = 14):
        self.period = period
        self.ind = Indicators()
    def analyze(self, candles: List[Dict]) -> StrategyScore:
        if len(candles) < self.period + 5:
            return StrategyScore(
                name="rsi",
                score=0,
                direction=None,
                confidence=0.0,
                reason="Not enough candles"
            )
        closes = [c["close"] for c in candles]
        rsi_values = self.ind.rsi(closes, self.period)
        if not rsi_values:
            return StrategyScore(
                name="rsi",
                score=0,
                direction=None,
                confidence=0.0,
                reason="RSI unavailable"
            )
        current_rsi = rsi_values[-1]
        score = 0
        direction = None
        confidence = 0.5
        reason = ""
        # ===== Mean Reversion =====
        if current_rsi < 25:
            score += 2
            direction = "LONG"
            confidence = 0.7
            reason = f"RSI oversold ({current_rsi:.1f})"
        elif current_rsi > 75:
            score += 2
            direction = "SHORT"
            confidence = 0.7
            reason = f"RSI overbought ({current_rsi:.1f})"
        # ===== Momentum Continuation =====
        elif current_rsi > 60:
            score += 1
            direction = "LONG"
            confidence = 0.6
            reason = f"RSI bullish momentum ({current_rsi:.1f})"
        elif current_rsi < 40:
            score += 1
            direction = "SHORT"
            confidence = 0.6
            reason = f"RSI bearish momentum ({current_rsi:.1f})"
        else:
            reason = f"RSI neutral ({current_rsi:.1f})"
        return StrategyScore(
            name="rsi",
            score=score,
            direction=direction,
            confidence=confidence,
            reason=reason,
            meta={"rsi": round(current_rsi, 2)}
        )
_

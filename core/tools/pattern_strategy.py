from typing import List, Dict
from core.tools.patterns_engine import PatternsEngine, PatternSignal
from core.tools.strategy_scores import StrategyScore
class PatternStrategy:
    def __init__(self):
        self.engine = PatternsEngine()
    def analyze(self, candles: List[Dict]) -> StrategyScore:
        patterns: List[PatternSignal] = self.engine.analyze(candles)
        if not patterns:
            return StrategyScore(
                name="patterns",
                score=0,
                direction=None,
                confidence=0.0,
                reason="No pattern detected"
            )
        # نختار أقوى نمط حسب strength
        best = max(patterns, key=lambda p: p.strength)
        score = best.strength
        direction = best.direction
        confidence = best.confidence
        return StrategyScore(
            name="patterns",
            score=score,
            direction=direction,
            confidence=confidence,
            reason=best.reason,
            meta={
                "pattern": best.pattern,
                "meta": best.meta
            }
        )

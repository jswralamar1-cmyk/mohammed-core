from typing import List, Dict
from core.tools.momentum_engine import MomentumEngine
from core.tools.strategy_scores import StrategyScore

class MomentumStrategy:

    def __init__(self):
        self.engine = MomentumEngine()

    def analyze(self, candles: List[Dict]) -> StrategyScore:
        analysis = self.engine.analyze(candles)
        score = analysis.get("score", 0)
        direction = analysis.get("direction")

        return StrategyScore(
            name="momentum",
            score=score,
            direction=direction,
            confidence=0.7, # Example confidence
            reason=f"Momentum score is {score}"
        )

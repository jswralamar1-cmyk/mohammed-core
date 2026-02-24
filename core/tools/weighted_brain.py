from typing import List, Dict
from core.tools.strategy_scores import StrategyScore
class WeightedBrain:
    def __init__(self, config: dict):
        self.config = config
    def evaluate(self, scores: List[StrategyScore]) -> Dict:
        long_total = 0.0
        short_total = 0.0
        details = []
        for s in scores:
            weight = self.config["strategy_weights"].get(s.name, 0.0)
            weighted_score = s.score * weight
            details.append({
                "strategy": s.name,
                "score": s.score,
                "weight": weight,
                "weighted_score": weighted_score,
                "direction": s.direction,
                "reason": s.reason
            })
            if s.direction == "LONG":
                long_total += weighted_score
            elif s.direction == "SHORT":
                short_total += weighted_score
        decision = None
        final_score = 0
        # Conflict Policy: dominant
        if self.config["conflict_policy"] == "dominant":
            if long_total > short_total:
                final_score = long_total - short_total
                if final_score >= self.config["scanner"]["entry_threshold"]:
                    decision = "LONG"
            elif short_total > long_total:
                final_score = short_total - long_total
                if final_score >= self.config["scanner"]["entry_threshold"]:
                    decision = "SHORT"
        return {
            "decision": decision,
            "final_score": final_score,
            "long_score": long_total,
            "short_score": short_total,
            "details": details
        }

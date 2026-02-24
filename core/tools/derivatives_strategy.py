from core.tools.strategy_scores import StrategyScore
from core.tools.derivatives_data import DerivativesData
class DerivativesStrategy:
    def __init__(self):
        self.data = DerivativesData()
    def analyze(self, symbol: str) -> StrategyScore:
        funding = self.data.get_funding_rate(symbol)
        oi = self.data.get_open_interest(symbol)
        score = 0
        direction = None
        confidence = 0.5
        reason = ""
        # ===== Funding Analysis =====
        # Highly positive funding → crowded LONG → risk of drop
        if funding > 0.001: # Adjusted for 1m
            score += 1.5
            direction = "SHORT"
            confidence = 0.6
            reason += f"Crowded LONG (funding {funding:.4f}) "
        # Highly negative funding → crowded SHORT → risk of squeeze
        elif funding < -0.001: # Adjusted for 1m
            score += 1.5
            direction = "LONG"
            confidence = 0.6
            reason += f"Crowded SHORT (funding {funding:.4f}) "
        # Mild bias
        elif funding > 0.0005:
            score += 0.5
            direction = "SHORT"
            reason += "Mild long bias "
        elif funding < -0.0005:
            score += 0.5
            direction = "LONG"
            reason += "Mild short bias "
        # ===== Open Interest Influence =====
        # Rising OI usually confirms trend pressure
        # This logic is complex and needs historical data, so we keep it simple
        if oi > 0:
            score += 0.5
        if not reason:
            reason = f"Neutral funding ({funding:.4f})"
        return StrategyScore(
            name="funding_oi",
            score=score,
            direction=direction,
            confidence=confidence,
            reason=reason.strip(),
            meta={
                "funding": round(funding, 6),
                "open_interest": oi
            }
        )
_

class PositionSizer:

    def __init__(self, policy: dict):
        self.policy = policy

    def calculate(self, balance: float, sl_percentage: float) -> dict:
        risk_per_trade = self.policy["risk_per_trade"]
        leverage = self.policy["leverage"]

        # دولار
        risk_amount = balance * risk_per_trade

        # دولار
        position_size_usd = (risk_amount / sl_percentage) * leverage

        return {
            "position_size_usd": position_size_usd,
            "leverage": leverage,
            "risk_amount_usd": risk_amount
        }

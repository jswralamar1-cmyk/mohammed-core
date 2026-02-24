class AdaptiveWeights:
    def __init__(self, memory, brain_config):
        self.memory = memory
        self.config = brain_config
        self.min_weight = 0.2
        self.max_weight = 2.0
        self.adjustment_rate = 0.05  # 5% per adjustment
    def adjust(self):
        stats = self.memory.state.get("strategy_stats", {})
        weights = self.config["weights"]
        for name, data in stats.items():
            total = data.get("total", 0)
            if total < 10:
                # لا نعدل إذا البيانات قليلة
                continue
            wins = data.get("wins", 0)
            win_rate = wins / total if total > 0 else 0
            current_weight = weights.get(name, 1.0)
            # Strong performer
            if win_rate > 0.6:
                new_weight = current_weight * (1 + self.adjustment_rate)
            # Weak performer
            elif win_rate < 0.4:
                new_weight = current_weight * (1 - self.adjustment_rate)
            else:
                continue  # no change
            # Clamp
            new_weight = max(self.min_weight, min(self.max_weight, new_weight))
            weights[name] = round(new_weight, 3)
        self.memory.save()
_

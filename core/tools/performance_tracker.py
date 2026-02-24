from collections import defaultdict
class PerformanceTracker:
    def __init__(self, memory):
        self.memory = memory
        if "strategy_stats" not in self.memory.state:
            self.memory.state["strategy_stats"] = defaultdict(lambda: {
                "wins": 0,
                "losses": 0,
                "total": 0
            })
    def record_trade_result(self, brain_dump: dict, pnl: float):
        """
        brain_dump = output from WeightedBrain
        pnl = profit/loss in percentage
        """
        win = pnl > 0
        for detail in brain_dump.get("details", []):
            name = detail["strategy"]
            weighted = detail["weighted_score"]
            # فقط الاستراتيجيات اللي فعلاً أثرت
            if weighted == 0:
                continue
            stats = self.memory.state["strategy_stats"][name]
            stats["total"] += 1
            if win:
                stats["wins"] += 1
            else:
                stats["losses"] += 1
        self.memory.save()
_

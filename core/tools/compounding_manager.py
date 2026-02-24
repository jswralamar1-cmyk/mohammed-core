import time
class CompoundingManager:
    def __init__(self, memory, base_risk=0.025):
        self.memory = memory
        self.base_risk = base_risk
        self.max_risk = 0.04
        if "win_streak" not in self.memory.state:
            self.memory.state["win_streak"] = 0
        if "risk_boost_until" not in self.memory.state:
            self.memory.state["risk_boost_until"] = 0
    def record_result(self, pnl):
        now = int(time.time())
        if pnl > 0:
            self.memory.state["win_streak"] += 1
            if self.memory.state["win_streak"] >= 3:
                self.memory.state["risk_boost_until"] = now + 1200  # 20 min boost
        else:
            self.memory.state["win_streak"] = 0
            self.memory.state["risk_boost_until"] = 0
        self.memory.save()
    def current_risk(self):
        now = int(time.time())
        if now < self.memory.state.get("risk_boost_until", 0):
            return self.max_risk
        streak = self.memory.state.get("win_streak", 0)
        if streak == 0:
            return self.base_risk
        elif streak == 1:
            return self.base_risk * 1.1 # 2.75%
        elif streak == 2:
            return self.base_risk * 1.2 # 3.0%
        else:
            return self.base_risk
_

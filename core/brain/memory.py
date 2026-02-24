import json
import copy
from pathlib import Path
from datetime import datetime, timezone
DEFAULT_STATE = {
    "date": None,
    "daily_pnl": 0.0,
    "trades_today": 0,
    "open_positions": {},
    "trade_history": [],
    "last_user_messages": [],
    "strategy_stats": {},
    "win_streak": 0,
    "risk_boost_until": 0
}
class Memory:
    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.state = self._load_state()
        self._check_new_day()
    def _load_state(self):
        if self.data_path.exists():
            with open(self.data_path, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return DEFAULT_STATE.copy()
        else:
            return copy.deepcopy(DEFAULT_STATE)
    def save(self):
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)
    def _check_new_day(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self.state.get("date") != today:
            self.state["date"] = today
            self.state["daily_pnl"] = 0.0
            self.state["trades_today"] = 0
            self.state["trade_history"] = []
            # Do NOT reset open_positions on new day - they may still be open
            self.save()
    def record_trade(self, trade_data: dict):
        self.state["trade_history"].append(trade_data)
        self.state["trades_today"] += 1
        self.save()
    def update_pnl(self, pnl: float):
        self.state["daily_pnl"] += pnl
        self.save()
    def add_open_position(self, symbol: str, position_data: dict):
        self.state["open_positions"][symbol] = position_data
        self.save()
    def remove_open_position(self, symbol: str):
        if symbol in self.state["open_positions"]:
            del self.state["open_positions"][symbol]
            self.save()
    def add_user_message(self, text: str):
        msgs = self.state.get("last_user_messages", [])
        msgs.append(text)
        self.state["last_user_messages"] = msgs[-30:]
        self.save()

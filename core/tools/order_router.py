from dataclasses import dataclass
from typing import Optional
from core.tools.execution_guard import ExecutionGuard, TradeSignal
from core.brain.memory import Memory
class OrderRouter:
    def __init__(self, policy: dict, memory: Memory):
        self.policy = policy
        self.memory = memory
        self.guard = ExecutionGuard(policy, memory)
    def route(self, signal: TradeSignal):
        success, status, order = self.guard.execute_market(signal)
        return {
            "success": success,
            "status": status,
            "order": order
        }

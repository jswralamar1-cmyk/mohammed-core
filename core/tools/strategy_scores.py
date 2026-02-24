from dataclasses import dataclass, field
from typing import Optional, Dict
@dataclass
class StrategyScore:
    name: str
    score: float
    direction: Optional[str]
    confidence: float
    reason: str
    meta: Optional[Dict] = field(default_factory=dict)

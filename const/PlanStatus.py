# core/PlanStatus.py
from enum import Enum

class PlanStatus(str, Enum):
    PLANNED = "PLANNED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    TRIGGERED = "TRIGGERED"
    EXPIRED = "EXPIRED"
    HOLD = "HOLD"  # New status for 7-day hold

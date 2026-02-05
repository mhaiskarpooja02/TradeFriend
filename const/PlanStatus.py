# core/PlanStatus.py
from enum import Enum

class PlanStatus(str, Enum):
    PLANNED = "PLANNED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    TRIGGERED = "TRIGGERED"
    EXPIRED = "EXPIRED"
    HOLD = "HOLD"  # New status for 7-day hold

class TradeStatus(str, Enum):
    READY   = "READY"     # waiting for entry trigger
    PARTIAL = "PARTIAL"   # entry in progress
    OPEN    = "OPEN"      # fully entered
    EXITED  = "EXITED"
    INVALID = "INVALID"

class HoldMode(int, Enum):
    OPEN    = 0   # no partial booking yet
    PARTIAL = 1   # partial profit booked
    RUNNER  = 2   # runner mode
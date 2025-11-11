# strategy/base_strategy.py

from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """Abstract base class for all strategies."""

    def __init__(self, df, buy_price: float, qty: int, symbol: str = None):
        self.df = df
        self.buy_price = buy_price
        self.qty = qty
        self.symbol = symbol

    @abstractmethod
    def analyze(self) -> dict:
        """Run analysis and return structured report as dict"""
        pass

    @abstractmethod
    def format_report(self, report: dict) -> str:
        """Convert dict report into human-readable formatted string"""
        pass

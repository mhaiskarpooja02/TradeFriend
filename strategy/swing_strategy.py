# strategy/swing_strategy.py
from .base_strategy import BaseStrategy

class SwingStrategy(BaseStrategy):
    def analyze(self) -> dict:
        report = {
            "symbol": self.symbol,
            "buy_price": self.buy_price,
            "qty": self.qty,
            "targets": [self.buy_price * 1.05, self.buy_price * 1.1],
            "stop_loss": self.buy_price * 0.95,
            "holding_period": "1-4 weeks"
        }
        return report

    @staticmethod
    def format_report(report: dict) -> str:
        return (
            f"📊 Swing Trade Plan for {report['symbol']}\n"
            f"Buy Price: {report['buy_price']}\n"
            f"Quantity: {report['qty']}\n"
            f"Targets: {', '.join(str(t) for t in report['targets'])}\n"
            f"Stop Loss: {report['stop_loss']}\n"
            f"Holding Period: {report['holding_period']}\n"
        )

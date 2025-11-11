# strategy/intraday_strategy.py
from .base_strategy import BaseStrategy

class IntradayStrategy(BaseStrategy):
    def analyze(self) -> dict:
        report = {
            "symbol": self.symbol,
            "buy_price": self.buy_price,
            "qty": self.qty,
            "targets": [self.buy_price * 1.01, self.buy_price * 1.02],
            "stop_loss": self.buy_price * 0.99,
            "holding_period": "Intraday"
        }
        return report

    @staticmethod
    def format_report(report: dict) -> str:
        return (
            f"⚡ Intraday Plan for {report['symbol']}\n"
            f"Buy Price: {report['buy_price']}\n"
            f"Quantity: {report['qty']}\n"
            f"Targets: {', '.join(str(t) for t in report['targets'])}\n"
            f"Stop Loss: {report['stop_loss']}\n"
            f"Holding Period: {report['holding_period']}\n"
        )

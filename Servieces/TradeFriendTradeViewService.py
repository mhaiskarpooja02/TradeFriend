# runner/TradeFriendTradeViewService.py

from utils.logger import get_logger

logger = get_logger(__name__)


class TradeFriendTradeViewService:

    # ==================================================
    # ACTIVE TRADE ROW (Dashboard)
    # ==================================================
    @staticmethod
   
    def active_trade_row(trade, ltp):
       
        logger.info(
        "📊 active_trade_row started | symbol=%s | ltp=%s | status=%s",
        trade.get("symbol"),
        ltp,
        trade.get("status")
        )
        try:
            entry = float(trade["entry"])
            sl = float(trade["sl"])
            target = float(trade["target"])
            qty = int(trade["qty"])
            status = trade["status"]
    
            risk = abs(entry - sl)
            pnl = round((ltp - entry) * qty, 2) if ltp else "--"
    
            r_mult = (
                round((ltp - entry) / risk, 2)
                if ltp and risk > 0 else "--"
            )
    
            progress = "--"
            if ltp and target != entry:
                progress = f"{round(((ltp - entry) / (target - entry)) * 100, 1)}%"
    
            tag = ""
            if isinstance(pnl, (int, float)):
                if pnl > 0:
                    tag = "profit"
                elif pnl < 0:
                    tag = "loss"
    
            return {
                "values": (
                    trade["symbol"],
                    round(entry, 2),
                    ltp or "--",
                    round(sl, 2),
                    round(target, 2),
                    qty,
                    pnl,
                    r_mult,
                    progress,
                    status
                ),
                "tag": tag
            }
    
        except Exception as e:
            logger.exception(
                f"Active row build failed | trade={trade} | ltp={ltp}"
            )
            return None

    # ==================================================
    # HISTORY TRADE ROW
    # ==================================================
    @staticmethod
    def history_trade_row(trade):
        try:
            entry = float(trade["entry"])
            exit_price = float(trade["exit_price"])
            qty = int(trade["qty"])

            pnl = round((exit_price - entry) * qty, 2)
            risk = abs(entry - float(trade["sl"])) or 1
            r_mult = round((exit_price - entry) / risk, 2)

            row = (
                trade["symbol"],
                round(entry, 2),
                round(exit_price, 2),
                qty,
                pnl,
                r_mult,
                trade["exit_reason"],
                trade["closed_on"]
            )

            logger.debug(
                f"History row built | {trade['symbol']} | "
                f"Exit={exit_price} | PnL={pnl} | R={r_mult}"
            )

            return row

        except Exception as e:
            logger.exception(
                f"Failed to build history trade row | trade={trade}"
            )
            return None

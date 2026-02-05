# core/TradeFriendSwingTradeMonitor.py

from utils.logger import get_logger
from core.TradeFriendDataProvider import TradeFriendDataProvider
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from Servieces.TradeFriendExitOrderService import TradeFriendExitOrderService
from db.TradeFriendOrderConfigRepo import TradeFriendOrderConfigRepo
from config.TradeFriendConfig import (
    ALLOW_TRAILING_SL,
    ENABLE_PARTIAL_BOOKING,
)

logger = get_logger(__name__)


class TradeFriendSwingTradeMonitor:
    """
    PURPOSE:
    - Monitor OPEN / PARTIAL swing trades
    - Decide EXACTLY ONE exit per trade per cycle (LOCKED)
    - Execute via PAPER or LIVE safely
    """

    def __init__(self):
        self.provider = TradeFriendDataProvider()
        self.trade_repo = TradeFriendTradeRepo()
        self.exit_oms = TradeFriendExitOrderService()
        self.order_config = TradeFriendOrderConfigRepo()

    # ==================================================
    # PUBLIC ENTRY
    # ==================================================
    def run(self):
        """📌 Iterate all OPEN / PARTIAL trades"""
        open_trades = self.trade_repo.fetch_open_trades()
        if not open_trades:
            return

        for trade in open_trades:
            try:
                self._process_trade(dict(trade))
            except Exception as e:
                logger.exception(
                    f"SwingTradeMonitor failed for {trade['symbol']}: {e}"
                )

    # ==================================================
    # PROCESS SINGLE TRADE
    # ==================================================
    def _process_trade(self, trade: dict):
        """📌 Decide ONE exit (or none) for this trade"""

        symbol = trade["symbol"]
        trade_id = trade["id"]

        entry = float(trade["entry"])
        sl = float(trade["sl"])
        target = float(trade["target"])

        initial_qty = int(trade["initial_qty"])
        remaining_qty = int(trade["remaining_qty"])
        hold_mode = int(trade.get("hold_mode", 0))

        if remaining_qty <= 0:
            return

        # -------------------------------
        # Fetch LTP (always latest)
        # -------------------------------
        ltp = self.provider.get_ltp_byLtp(symbol)
        if ltp is None:
            return

        logger.info(
            f"🔍 MONITOR | {symbol} | LTP={ltp} | ENTRY={entry} | "
            f"SL={sl} | TARGET={target} | HOLD={hold_mode} | REM_QTY={remaining_qty}"
        )

        # ==================================================
        # 1️⃣ HARD SL — FINAL EXIT (TOP PRIORITY)
        # ==================================================
        if ltp <= sl:
            self._final_exit(trade, "SL_HIT", remaining_qty, ltp)
            return  # 🔒 lock cycle

        # ==================================================
        # 2️⃣ PARTIAL PROFIT — DECIDE ONE EXIT ONLY
        # ==================================================
        if ENABLE_PARTIAL_BOOKING and remaining_qty > 0:
            exited = self._process_partial_tiers(
                trade, ltp, entry, target, initial_qty, remaining_qty
            )
            if exited:
                return  # 🔒 one exit per trade per cycle

        # ==================================================
        # 3️⃣ TARGET → CONVERT TO RUNNER (NO EXIT)
        # ==================================================
        if ltp >= target and hold_mode == 1:
            self.trade_repo.update_sl(trade_id, target)
            self.trade_repo.update_hold_mode(trade_id, 2)
            logger.info(f"🏁 TARGET → RUNNER | {symbol}")
            return

        # ==================================================
        # 4️⃣ RUNNER TRAILING SL
        # ==================================================
        if ALLOW_TRAILING_SL and hold_mode == 2:
            new_sl = max(sl, ltp * 0.98)
            if new_sl > sl:
                self.trade_repo.update_sl(trade_id, new_sl)
                logger.info(f"🔒 RUNNER SL TRAILED | {symbol} → {new_sl}")

    # ==================================================
    # PARTIAL TIERS — DECISION FIRST, ONE EXIT
    # ==================================================
    def _process_partial_tiers(
        self,
        trade: dict,
        ltp: float,
        entry: float,
        target: float,
        initial_qty: int,
        remaining_qty: int
    ) -> bool:
        """
        📌 Decide highest eligible tier based on exited_qty and LTP
        """

        symbol = trade["symbol"]

        exited_qty = initial_qty - remaining_qty

        # -------------------------------
        # Build ¼ quantity plan safely
        # -------------------------------
        base_qty = initial_qty // 4
        if base_qty <= 0:
            return False

        remainder = initial_qty - (base_qty * 4)

        # Highest tier first (gap-safe)
        tiers = [
            ("PARTIAL_EXIT_75", 0.75, base_qty),
            ("PARTIAL_EXIT_50", 0.50, base_qty),
            ("PARTIAL_EXIT_25", 0.25, base_qty),
        ]

        for tier_name, tier_ratio, tier_qty in tiers:
            tier_price = entry + ((target - entry) * tier_ratio)
            required_exited = int(initial_qty * tier_ratio)

            # 🔐 Already crossed earlier
            if exited_qty >= required_exited:
                continue

            # 📈 Price condition met
            if ltp >= tier_price:
                final_exit_qty = min(tier_qty, remaining_qty)

                # 🧮 Add remainder only on LAST exit
                if final_exit_qty == remaining_qty:
                    final_exit_qty += remainder

                self._execute_exit(
                    trade,
                    tier_name,
                    final_exit_qty,
                    ltp
                )

                logger.info(
                    f"📉 PARTIAL EXIT | {symbol} | {tier_name} | "
                    f"QTY={final_exit_qty} @ {ltp}"
                )
                return True  # 🔒 EXIT LOCK

            # ❌ Price not eligible → stop lower tiers
            break

        return False

    # ==================================================
    # EXECUTE EXIT — PAPER / LIVE SAFE
    # ==================================================
    def _execute_exit(self, trade: dict, reason: str, qty: int, price: float):
        """
        📌 Execute exit safely using existing repo / OMS contracts
        """

        trade_id = trade["id"]
        symbol = trade["symbol"]

        if qty <= 0:
            return

        # =====================
        # PAPER MODE
        # =====================
        if not self.order_config.is_live():
            # Repo owns qty, capital & hold_mode updates
            self.trade_repo.mark_partial_exit(
                trade_id=trade_id,
                exit_qty=qty,
                exit_price=price
            )
            return

        # =====================
        # LIVE MODE
        # =====================
        resp = self.exit_oms.place_exit_order(
            trade_id=trade_id,
            symbol=symbol,
            exit_qty=qty,
            exit_reason=reason,
            exit_price=price
        )

        if not resp or resp.get("status") != "SUCCESS":
            logger.warning(f"❌ LIVE EXIT FAILED | {symbol} | {reason}")
            return

        # ✅ IMPORTANT:
        # Repo update is handled by OMS success flow
        # Monitor MUST NOT update trade table here

    # ==================================================
    # FINAL EXIT — SL / FULL CLOSE
    # ==================================================
    def _final_exit(self, trade: dict, reason: str, qty: int, price: float):
        """
        📌 Final exit — close and archive trade
        """

        trade_id = trade["id"]
        symbol = trade["symbol"]

        if not self.order_config.is_live():
            self.trade_repo.close_and_archive(trade_id, price, reason)
            return

        self.exit_oms.place_exit_order(
            trade_id=trade_id,
            symbol=symbol,
            exit_qty=qty,
            exit_reason=reason,
            exit_price=price
        )

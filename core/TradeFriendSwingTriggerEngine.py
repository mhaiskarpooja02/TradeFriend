# core/TradeFriendSwingTriggerEngine.py

import logging
from datetime import datetime
from Servieces import TradeFriendOrderManagementService
from core.TradeFriendDataProvider import TradeFriendDataProvider
from core.TradeFriendPositionSizer import TradeFriendPositionSizer
from brokers.dhan_client import DhanClient
logger = logging.getLogger(__name__)


class TradeFriendSwingTriggerEngine:
    """
    PURPOSE:
    - Monitor LTP during market hours
    - Trigger swing trades when entry price is hit
    - Uses FIXED QTY by PRICE SLABS (via PositionSizer)
    - Supports PAPER / LIVE trading
    """

    def __init__(
        self,
        swing_plan_repo,
        trade_repo,
        capital: float,
        paper_trade: bool = True
    ):
        self.swing_plan_repo = swing_plan_repo
        self.trade_repo = trade_repo
        self.capital = capital
        self.paper_trade = paper_trade

        self.provider = TradeFriendDataProvider()
        self.sizer = TradeFriendPositionSizer()
        # 🔥 Execution client (ONLY for LIVE)
        self.broker = DhanClient() if not paper_trade else None
        self.oms = TradeFriendOrderManagementService()

    # -----------------------------------
    # MAIN RUN METHOD
    # -----------------------------------
    def run(self):
        logger.info("📡 Swing Trigger Engine started")

        plans = self.swing_plan_repo.fetch_active_plans()
        if not plans:
            logger.info("No active swing plans")
            return

        for plan in plans:
            try:
                self._process_plan(dict(plan))  # normalize sqlite Row
            except Exception as e:
                logger.exception(
                    f"Trigger failed for {plan['symbol']}: {e}"
                )

        logger.info("✅ Swing Trigger Engine completed")

    # -----------------------------------
    # PROCESS SINGLE PLAN
    # -----------------------------------
    def _process_plan(self, plan: dict):
        symbol = plan["symbol"]
        entry = float(plan["entry"])
        sl = float(plan["sl"])
        target = float(plan.get("target1") or 0)

        logger.info(f"Checking swing trigger → {symbol}")

        # ---------------- EXPIRY CHECK ----------------
        expiry = plan.get("expiry_date")
        if expiry:
            if expiry < datetime.now().date().isoformat():
                logger.info(f"⌛ Plan expired | {symbol}")
                return

        # ---------------- FETCH LTP ----------------
        ltp = self.provider.get_ltp(symbol)
        if not ltp or ltp <= 0:
            logger.warning(f"{symbol} → Invalid LTP")
            return

        # ---------------- RISK VALIDATION ----------------
        risk = entry - sl
        if risk <= 0:
            logger.warning(f"{symbol} → Invalid SL / risk")
            return

        # ---------------- GAP FILTER ----------------
        if ltp > entry + risk:
            logger.warning(
                f"⚠️ GAP SKIP | {symbol} | LTP={ltp} Entry={entry}"
            )
            return

        # ---------------- ENTRY CONDITION ----------------
        if ltp < entry:
            logger.info(f"⏳ Waiting | {symbol} | LTP={ltp}")
            return

        logger.info(
            f"🚀 ENTRY HIT | {symbol} | LTP={ltp} ≥ Entry={entry}"
        )

        # ---------------- POSITION SIZING ----------------
        try:
            sizing = self.sizer.calculate(entry_price=entry)
        except Exception as e:
            logger.warning(f"{symbol} → Sizing failed | {e}")
            return

        qty = sizing["qty"]
        position_value = sizing["position_value"]

        if qty <= 0:
            logger.warning(f"{symbol} → Qty zero after sizing")
            return
        
        # ---------------- DUPLICATE TRADE CHECK ----------------
        if self.trade_repo.has_active_trade(symbol):
            logger.warning(
                f"⛔ DUPLICATE BLOCKED | {symbol} | Active trade already exists"
            )
            return

        # ---------------- SAVE TRADE ----------------
        trade = {
            "symbol": symbol,
            "entry": entry,
            "sl": sl,
            "target1": target,
            "qty": qty,
            "position_value": position_value,
            "confidence": plan.get("rr", 0),
            "status": "PAPER" if self.paper_trade else "LIVE"
        }

        # ---------------- SAVE TRADE ----------------
        trade_id = self.trade_repo.save_trade(trade)

        self.oms.place_trade(
                trade_id=trade_id,
                symbol=symbol,
                qty=qty,
                side="BUY"
            )

        # ---------------- UPDATE PLAN STATUS ----------------
        self.swing_plan_repo.mark_triggered(plan["id"])

        logger.info(
            f"✅ SWING TRADE TRIGGERED | {symbol} | "
            f"Qty={qty} | PosValue={position_value} | "
            f"Mode={'PAPER' if self.paper_trade else 'LIVE'}"
        )

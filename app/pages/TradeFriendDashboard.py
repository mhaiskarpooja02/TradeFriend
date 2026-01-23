import threading
import tkinter.messagebox as messagebox
from tkinter import ttk, StringVar
from datetime import datetime, time

from core.TradeFriendDataProvider import TradeFriendDataProvider
from core.TradeFriendScheduler import TradeFriendScheduler
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendWatchlistRepo import TradeFriendWatchlistRepo
from db.TradeFriendTradeHistoryRepo import TradeFriendTradeHistoryRepo
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo
from utils.TradeFriendManager import TradeFriendManager
from Servieces.TradeFriendTradeViewService import TradeFriendTradeViewService
from utils.logger import get_logger

logger = get_logger(__name__)

class TradeFriendDashboard(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)

        # ---------------- Repos / Services ----------------
        self.watchlist_repo = TradeFriendWatchlistRepo()
        self.trade_repo = TradeFriendTradeRepo()
        self.trade_history_repo = TradeFriendTradeHistoryRepo()
        self.settings_repo = TradeFriendSettingsRepo()

        self.manager = TradeFriendManager()
        self.provider = TradeFriendDataProvider()

        self.trade_mode = self.settings_repo.get_trade_mode()
        self.ltp_cache = {}

        # ✅ BACKGROUND SCHEDULER
        self.scheduler = TradeFriendScheduler(
            manager=self.manager,
            trade_mode=self.trade_mode
        )
        self.scheduler.start()

        self._build_ui()
        self.refresh_data()

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):

        # ---------- Loading ----------
        self.loading_var = StringVar(value="")
        loading_frame = ttk.Frame(self)
        loading_frame.pack(fill="x", padx=6)

        ttk.Label(loading_frame, textvariable=self.loading_var,
                  foreground="blue").pack(side="left", padx=6)

        self.progress = ttk.Progressbar(
            loading_frame, mode="indeterminate", length=200
        )
        self.progress.pack(side="left", padx=6)

        # ---------- KPI ----------
        self.kpi_frame = ttk.Frame(self)
        self.kpi_frame.pack(fill="x", padx=8, pady=6)

        self.kpi_labels = {}
        for key in [
            "capital", "swing_used", "swing_available",
            "active", "profit", "loss", "pnl"
        ]:
            lbl = ttk.Label(
                self.kpi_frame, text="--", background="white",
                anchor="center", font=("Segoe UI", 11, "bold"), padding=8
            )
            lbl.pack(side="left", expand=True, fill="x", padx=4)
            self.kpi_labels[key] = lbl

        # ---------- Controls ----------
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=6, pady=6)

        # ---------- Manual Automation ----------
        self.manual_mode = StringVar(value="FULL")

        ttk.Combobox(
            bar,
            textvariable=self.manual_mode,
            values=["DAILYSCAN","DECISION", "MORNING", "FULL"],
            width=12,
            state="readonly"
        ).pack(side="left", padx=5)

        ttk.Button(
            bar,
            text="🛠️ Run Manual",
            command=self.run_manual_wrapper  
        ).pack(side="left", padx=5)

        ttk.Button(bar, text="🔄 Refresh",
                   command=self.refresh_data).pack(side="right", padx=5)

        self.mode_btn = ttk.Button(bar, command=self.toggle_trade_mode)
        self.mode_btn.pack(side="right", padx=5)
        self._update_trade_mode_btn()

        # ---------- Tabs ----------
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self.watchlist_tab = ttk.Frame(notebook)
        self.trades_tab = ttk.Frame(notebook)
        self.history_tab = ttk.Frame(notebook)

        notebook.add(self.watchlist_tab, text="📋 Watchlist")
        notebook.add(self.trades_tab, text="📈 Active Trades")
        notebook.add(self.history_tab, text="📜 History")

        self._build_watchlist()
        self._build_trades()
        self._build_history()

    # =====================================================
    # TABLES
    # =====================================================

    def _build_watchlist(self):
        cols = ("symbol", "strategy", "bias", "scanned_on", "status")
        self.watchlist_table = ttk.Treeview(
            self.watchlist_tab, columns=cols, show="headings"
        )
        for c in cols:
            self.watchlist_table.heading(c, text=c.upper())
            self.watchlist_table.column(c, width=120, anchor="center")
        self.watchlist_table.pack(fill="both", expand=True, padx=6, pady=6)

    def _build_trades(self):
        cols = (
            "symbol", "entry", "ltp", "sl", "target",
            "qty", "pnl", "r", "progress", "status"
        )
        self.trades_table = ttk.Treeview(
            self.trades_tab, columns=cols, show="headings"
        )
        for c in cols:
            self.trades_table.heading(c, text=c.upper())
            self.trades_table.column(c, width=100, anchor="center")

        self.trades_table.tag_configure("profit", foreground="green")
        self.trades_table.tag_configure("loss", foreground="red")
        self.trades_table.tag_configure("near", foreground="orange")
        self.trades_table.pack(fill="both", expand=True, padx=6, pady=6)

    def _build_history(self):
        cols = (
            "symbol", "entry", "exit_price", "qty",
            "pnl", "r", "exit_reason", "closed_on"
        )
        self.history_table = ttk.Treeview(
            self.history_tab, columns=cols, show="headings"
        )
        for c in cols:
            self.history_table.heading(c, text=c.upper())
            self.history_table.column(c, width=110, anchor="center")
        self.history_table.pack(fill="both", expand=True, padx=6, pady=6)

    # =====================================================
    # DATA LOADING
    # =====================================================

    def refresh_data(self):
        self._start_loading("Refreshing dashboard...")
        threading.Thread(
            target=self._load_data_bg, daemon=True
        ).start()

    def _load_data_bg(self):
        try:
            watchlist = self.watchlist_repo.fetch_all()
            active = self.trade_repo.fetch_active_trades()
            history = self.trade_history_repo.fetch_recent_closed()

            # ---------------- KPI (ACTIVE ONLY) ----------------
            total_pnl = 0.0
            win = 0
            loss = 0

            for row in active:
                try:
                    t = dict(row)

                    symbol = t.get("symbol")
                    entry = t.get("entry")
                    qty = t.get("qty")

                    if not symbol or entry is None or qty is None:
                        continue

                    ltp = self._get_ltp_cached(symbol)
                    if ltp is None:
                        continue

                    pnl = (ltp - entry) * qty
                    total_pnl += pnl

                    if pnl > 0:
                        win += 1
                    elif pnl < 0:
                        loss += 1

                except Exception as e:
                    print(f"❌ KPI calc error | {t.get('symbol')} | {e}")

            active_count = len(active)

            # ---------------- UI THREAD ----------------
            self.after(0, lambda: self._update_watchlist(watchlist))
            self.after(0, lambda: self._update_active_trades(active))
            self.after(0, lambda: self._update_history(history))
            self.after(
                0,
                lambda: self._update_kpis(
                    total_pnl=total_pnl,
                    active=active_count,
                    win=win,
                    loss=loss
                )
            )

        finally:
            self.after(0, self._stop_loading)

    # =====================================================
    # UI UPDATES
    # =====================================================

    def _update_watchlist(self, rows):
        self.watchlist_table.delete(*self.watchlist_table.get_children())
        for r in rows:
            self.watchlist_table.insert("", "end", values=(
                r["symbol"], r["strategy"], r["bias"],
                r["scanned_on"], r["status"]
            ))

    def _update_active_trades(self, active_trades):
        """
        Populate Active Trades table.
    
        Rules:
        - DB provides FACTS only
        - LTP, PnL, R, Progress are computed at runtime
        - Uses TradeFriendTradeViewService as single source of truth
        """
    
        # 🔐 Safety: table may not be initialized yet
        if not hasattr(self, "trades_table"):
            return
    
        # Clear table
        self.trades_table.delete(*self.trades_table.get_children())
    
        for trade in active_trades:
            try:
                # -------------------------------
                # Normalize sqlite3.Row → dict
                # -------------------------------
                trade = dict(trade)
    
                symbol = trade.get("symbol")
                if not symbol:
                    continue
                
                # -------------------------------
                # Fetch LTP (cached)
                # -------------------------------
                ltp = self._get_ltp_cached(symbol)
    
                # -------------------------------
                # Build UI row (SINGLE AUTHORITY)
                # -------------------------------
                row = TradeFriendTradeViewService.active_trade_row(
                    trade=trade,
                    ltp=ltp
                )
    
                # -------------------------------
                # Insert into table
                # -------------------------------
                self.trades_table.insert(
                    "",
                    "end",
                    values=row["values"],
                    tags=(row["tag"],)
                )
    
            except Exception as e:
                print(
                    f"❌ Failed to bind active trade row | "
                    f"symbol={trade.get('symbol')} | error={e}"
                )


    def _update_history(self, trades):
        self.history_table.delete(*self.history_table.get_children())
        for t in trades:
            self.history_table.insert(
                "", "end",
                values=TradeFriendTradeViewService.history_trade_row(t)
            )

    # =====================================================
    # KPI
    # =====================================================

    def _update_kpis(self, total_pnl, active, win, loss):
        s = self.settings_repo.fetch()

        total = s["total_capital"] or 0
        max_swing = s["max_swing_capital"] or 0
        free = s["available_swing_capital"] or 0
        used = round(max_swing - free, 2)

        self.kpi_labels["capital"].config(text=f"💰 Total: {total}",foreground="black")
        self.kpi_labels["swing_used"].config(text=f"🔒 Used: {used}",foreground="black")
        self.kpi_labels["swing_available"].config(text=f"🟢 Free: {free}",foreground="black")
        self.kpi_labels["active"].config(text=f"📊 Active: {active}",foreground="black")
        self.kpi_labels["profit"].config(text=f"🟢 Wins: {win}",foreground="green")
        self.kpi_labels["loss"].config(text=f"🔴 Loss: {loss}",foreground="red")
        self.kpi_labels["pnl"].config(
            text=f"💵 PnL: {round(total_pnl, 2)}",
            foreground="green" if total_pnl >= 0 else "red"
        )

    # =====================================================
    # HELPERS
    # =====================================================

    from datetime import datetime, time


    def _get_ltp_cached(self, symbol):
        # now = datetime.now()
        # weekday = now.weekday()   # 0=Mon, 6=Sun
        # current_time = now.time()

        # market_closed = (
        #     weekday in (5, 6) or                         # Sat, Sun
        #     current_time < time(9, 15) or                # Before market
        #     current_time > time(15, 30)                   # After market
        # )

        # # ---------------- Market Closed ----------------
        # if market_closed:
        #     cached = self.ltp_cache.get(symbol)
        #     return cached[0] if cached else None

        # ---------------- Market Open ----------------
        try:
            ltp = self.provider.get_ltp_byLtp(symbol)
            if ltp:
                #self.ltp_cache[symbol] = (ltp, now)
                return ltp
        except Exception:
            pass

        # ---------------- Fallback ----------------
        cached = self.ltp_cache.get(symbol)
        return cached[0] if cached else None


    def toggle_trade_mode(self):
        self.trade_mode = "LIVE" if self.trade_mode == "PAPER" else "PAPER"
        self.settings_repo.set_trade_mode(self.trade_mode)
        self._update_trade_mode_btn()
        messagebox.showinfo("Trade Mode", f"Mode set to {self.trade_mode}")

    def _update_trade_mode_btn(self):
        self.mode_btn.config(
            text="🟢 LIVE" if self.trade_mode == "LIVE" else "📝 PAPER"
        )

    # =====================================================
    # ACTIONS
    # =====================================================

    def run_daily_scan(self):
        self._run_bg(lambda: self.manager.tf_daily_scan(self.trade_mode))

    def run_morning_confirm(self):
        self._run_bg(lambda: self.manager.tf_morning_confirm(
            capital=100000, mode=self.trade_mode))

    def run_monitor(self):
        self._run_bg(lambda: self.manager.tf_monitor())

    def _run_bg(self, task):
        threading.Thread(
            target=lambda: (task(), self.after(0, self.refresh_data)),
            daemon=True
        ).start()

    def run_decision_runner(self):
        """
        Run DecisionRunner in background thread from UI
        """
        self._run_bg(lambda: self.manager.tf_decision_runner())

    # =====================================================
    # LOADING
    # =====================================================

    def _start_loading(self, msg):
        self.loading_var.set(msg)
        self.progress.start(10)
    def _stop_loading(self):
        self.progress.stop()
        self.loading_var.set("")

    # ---------------- Wrapper to pass selected flow ----------------
    def run_manual_wrapper(self):
        """
        Gets the selected flow from combobox and calls run_manual.
        """
        flow = self.manual_mode.get()
        self.run_manual(flow=flow, force=True)

    def run_manual(self, flow: str, force: bool = False):
        """
        Run manual automation based on the selected flow.
    
        flow options:
            - DAILYSCAN
            - DECISION
            - MORNING
            - FULL
        """
        logger.info(
            f"🛠 Manual run requested | flow={flow} | "
            f"trade_mode={self.trade_mode} | force={force}"
        )
    
        def task():
            if flow == "DAILYSCAN":
                self.manager.tf_daily_scan(self.trade_mode)
    
            elif flow == "DECISION":
                self.manager.tf_decision_runner()
    
            elif flow == "MORNING":
                self.manager.tf_morning_confirm(
                    capital=100000,   # or pull from settings
                    mode=self.trade_mode
                )
    
            elif flow == "FULL":
                # ✅ EXACT automated sequence
                self.manager.tf_daily_scan(self.trade_mode)
                self.manager.tf_decision_runner()
                self.manager.tf_morning_confirm(
                    capital=100000,
                    mode=self.trade_mode
                )
    
            else:
                logger.warning(f"Unknown manual flow: {flow}")
    
        self._run_bg(task)



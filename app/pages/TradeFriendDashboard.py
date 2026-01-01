import threading
import tkinter.messagebox as messagebox
from tkinter import ttk

from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendWatchlistRepo import TradeFriendWatchlistRepo
from utils.TradeFriendManager import TradeFriendManager


class TradeFriendDashboard(ttk.Frame):
    """
    TradeFriend Dashboard
    ---------------------
    - Watchlist
    - Executed Trades
    - Control buttons
    """

    def __init__(self, parent):
        super().__init__(parent)

        # ✅ DB repos (read-only for UI)
        self.watchlist_repo = TradeFriendWatchlistRepo()
        self.trade_repo = TradeFriendTradeRepo()

        # ✅ Central orchestrator
        self.manager = TradeFriendManager()

        self._build_ui()
        self.refresh_data()

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):

        # ---------- Control Bar ----------
        control_bar = ttk.Frame(self)
        control_bar.pack(fill="x", padx=6, pady=6)

        ttk.Button(
            control_bar,
            text="📊 Run Daily Scan",
            command=self.run_daily_scan
        ).pack(side="left", padx=5)

        ttk.Button(
            control_bar,
            text="🚀 Morning Confirmation",
            command=self.run_morning_confirm
        ).pack(side="left", padx=5)

        ttk.Button(
            control_bar,
            text="📈 Run Monitor",
            command=self.run_monitor
        ).pack(side="left", padx=5)

        ttk.Button(
            control_bar,
            text="🔄 Refresh",
            command=self.refresh_data
        ).pack(side="right", padx=5)

        # ---------- Tabs ----------
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self.watchlist_tab = ttk.Frame(notebook)
        self.trades_tab = ttk.Frame(notebook)

        notebook.add(self.watchlist_tab, text="📋 Watchlist")
        notebook.add(self.trades_tab, text="📈 Trades")

        self._build_watchlist()
        self._build_trades()

    # =====================================================
    # Tables
    # =====================================================

    def _build_watchlist(self):
        cols = ("symbol", "strategy", "bias", "scanned_on", "status")

        self.watchlist_table = ttk.Treeview(
            self.watchlist_tab,
            columns=cols,
            show="headings"
        )

        for c in cols:
            self.watchlist_table.heading(c, text=c.upper())
            self.watchlist_table.column(c, width=120, anchor="center")

        self.watchlist_table.pack(fill="both", expand=True, padx=6, pady=6)

    def _build_trades(self):
        cols = (
            "symbol", "entry", "sl", "target",
            "qty", "status", "pnl", "rr"
        )

        self.trades_table = ttk.Treeview(
            self.trades_tab,
            columns=cols,
            show="headings"
        )

        for c in cols:
            self.trades_table.heading(c, text=c.upper())
            self.trades_table.column(c, width=100, anchor="center")

        self.trades_table.pack(fill="both", expand=True, padx=6, pady=6)

    # =====================================================
    # Data Loaders
    # =====================================================

    def refresh_data(self):
        self._load_watchlist()
        self._load_trades()

    def _load_watchlist(self):
        self.watchlist_table.delete(*self.watchlist_table.get_children())

        for r in self.watchlist_repo.fetch_all():
            self.watchlist_table.insert(
                "",
                "end",
                values=(
                    r["symbol"],
                    r["strategy"],
                    r["bias"],
                    r["scanned_on"],
                    r["status"]
                )
            )

    def _load_trades(self):
        self.trades_table.delete(*self.trades_table.get_children())

        for r in self.trade_repo.fetch_recent_with_pnl(limit=50):

            entry = r["entry"]
            sl = r["sl"]
            target = r["target"]
            qty = r["qty"]
            status = r["status"]

            pnl = 0.0
            rr = 0.0

            if status == "TARGET_HIT":
                pnl = (target - entry) * r["initial_qty"]
                rr = round((target - entry) / (entry - sl), 2)

            elif status in ("SL_HIT", "SL_CLOSE_BASED", "EMERGENCY_EXIT"):
                pnl = (sl - entry) * r["initial_qty"]
                rr = -1.0

            self.trades_table.insert(
                "",
                "end",
                values=(
                    r["symbol"],
                    entry,
                    sl,
                    target,
                    qty,
                    status,
                    round(pnl, 2),
                    rr
                )
            )

    # =====================================================
    # Button Actions (THREAD SAFE)
    # =====================================================

    def run_daily_scan(self):
        self._run_threaded(
            title="Daily Scan Failed",
            task=self.manager.tf_daily_scan
        )

    def run_morning_confirm(self):
        self._run_threaded(
            title="Morning Confirmation Failed",
            task=lambda: self.manager.tf_morning_confirm(capital=100000)
        )

    def run_monitor(self):
        self._run_threaded(
            title="Trade Monitor Failed",
            task=self.manager.tf_monitor
        )

    # =====================================================
    # Thread helper
    # =====================================================

    def _run_threaded(self, task, title):
        def worker():
            try:
                task()
                self.after(0, self.refresh_data)
            except Exception as e:
                self.after(
                    0,
                    lambda err=str(e): messagebox.showerror(title, err)
                )

        threading.Thread(target=worker, daemon=True).start()

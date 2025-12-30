import tkinter as tk
from tkinter import ttk

from db.TradeFriendDatabase import TradeFriendDatabase
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendWatchlistRepo import TradeFriendWatchlistRepo
from core.watchlist_engine import WatchlistEngine
from core.TradeFriendDecisionRunner import TradeFriendDecisionRunner
import threading
import tkinter.messagebox as messagebox


class TradeFriendDashboard(ttk.Frame):
    """
    Data dashboard:
    - Watchlist
    - Planned Trades
    """

    def __init__(self, parent):
        super().__init__(parent)

        # ✅ Create DB & repos internally (like other pages)
        self.db = TradeFriendDatabase()
        self.watchlist_repo = TradeFriendWatchlistRepo(self.db)
        self.trade_repo = TradeFriendTradeRepo(self.db)

        self._build_ui()
        self.refresh_data()

    # ---------------- UI ----------------

    def _build_ui(self):

        # --- Control Bar ---
        control_bar = ttk.Frame(self)
        control_bar.pack(fill="x", padx=6, pady=6)

        ttk.Button(
            control_bar,
            text="Run Daily Scan",
            command=self.run_daily_scan
        ).pack(side="left", padx=5)

        ttk.Button(
            control_bar,
            text="Run Morning Confirmation",
            command=self.run_morning_confirm
        ).pack(side="left", padx=5)

        ttk.Button(
            control_bar,
            text="Refresh Tables",
            command=self.refresh_data
        ).pack(side="right", padx=5)


        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self.watchlist_tab = ttk.Frame(notebook)
        self.trades_tab = ttk.Frame(notebook)

        notebook.add(self.watchlist_tab, text="📋 Watchlist")
        notebook.add(self.trades_tab, text="📈 Planned Trades")

        self._build_watchlist()
        self._build_trades()

    def _build_watchlist(self):
        cols = ("symbol", "strategy", "bias", "scanned_on", "status")
        self.watchlist_table = ttk.Treeview(
            self.watchlist_tab, columns=cols, show="headings"
        )

        for c in cols:
            self.watchlist_table.heading(c, text=c.upper())
            self.watchlist_table.column(c, anchor="center", width=120)

        self.watchlist_table.pack(fill="both", expand=True, padx=6, pady=6)

    def _build_trades(self):
        cols = (
            "symbol", "entry", "sl", "target",
            "qty", "confidence", "status"
        )
        self.trades_table = ttk.Treeview(
            self.trades_tab, columns=cols, show="headings"
        )

        for c in cols:
            self.trades_table.heading(c, text=c.upper())
            self.trades_table.column(c, anchor="center", width=100)

        self.trades_table.pack(fill="both", expand=True, padx=6, pady=6)

    # ---------------- Data ----------------

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
    
        for r in self.trade_repo.fetch_recent(limit=50):
            self.trades_table.insert(
                "",
                "end",
                values=(
                    r["symbol"],
                    r["entry"],
                    r["sl"],
                    r["target"],
                    r["qty"],
                    r["confidence"],
                    r["status"]
                )
            )

    def run_daily_scan(self):
        print("🔥 Daily Scan button clicked")

        def worker():
            try:
                engine = WatchlistEngine()
                engine.run()
                print("✅ Daily Scan completed")

                # Refresh table after scan
                self.after(0, self.refresh_data)

            except Exception as e:
                print("❌ Daily Scan failed:", e)
                self.after(
                    0,
                    lambda: messagebox.showerror("Error", f"Daily scan failed: {e}")
                )

        threading.Thread(target=worker, daemon=True).start()


    def run_morning_confirm(self):
        print("🔥 Morning Confirm button clicked")

        def worker():
            try:
                CAPITAL = 100000
                runner = TradeFriendDecisionRunner(capital=CAPITAL)
                runner.run()
                print("✅ Morning Confirmation completed")

                self.after(0, self.refresh_data)

            except Exception as e:
                print("❌ Morning confirmation failed:", e)
                self.after(
                    0,
                    lambda: messagebox.showerror("Error", f"Morning confirmation failed: {e}")
                )

        threading.Thread(target=worker, daemon=True).start()
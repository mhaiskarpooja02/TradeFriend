import threading
import tkinter.messagebox as messagebox
from tkinter import ttk
from datetime import datetime, time

from core.TradeFriendDataProvider import TradeFriendDataProvider
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendWatchlistRepo import TradeFriendWatchlistRepo
from utils.TradeFriendManager import TradeFriendManager


class TradeFriendDashboard(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)

        self.watchlist_repo = TradeFriendWatchlistRepo()
        self.trade_repo = TradeFriendTradeRepo()
        self.manager = TradeFriendManager()
        self.provider = TradeFriendDataProvider()

        # 🔒 LTP CACHE {symbol: (ltp, timestamp)}
        self.ltp_cache = {}

        self._build_ui()
        self.refresh_data()

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):

        # ---------- KPI HEADER ----------
        self.kpi_frame = ttk.Frame(self)
        self.kpi_frame.pack(fill="x", padx=8, pady=6)

        self.kpi_labels = {}
        for key in ["capital", "active", "profit", "loss", "pnl"]:
            lbl = ttk.Label(
                self.kpi_frame,
                text="--",
                background="white",
                anchor="center",
                font=("Segoe UI", 11, "bold"),
                padding=8
            )
            lbl.pack(side="left", expand=True, fill="x", padx=4)
            self.kpi_labels[key] = lbl

        # ---------- CONTROL BAR ----------
        control_bar = ttk.Frame(self)
        control_bar.pack(fill="x", padx=6, pady=6)

        ttk.Button(control_bar, text="📊 Daily Scan", command=self.run_daily_scan).pack(side="left", padx=5)
        ttk.Button(control_bar, text="🚀 Morning Confirm", command=self.run_morning_confirm).pack(side="left", padx=5)
        ttk.Button(control_bar, text="📈 Monitor", command=self.run_monitor).pack(side="left", padx=5)
        ttk.Button(control_bar, text="🔄 Refresh", command=self.refresh_data).pack(side="right", padx=5)

        # ---------- TABS ----------
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self.watchlist_tab = ttk.Frame(notebook)
        self.trades_tab = ttk.Frame(notebook)

        notebook.add(self.watchlist_tab, text="📋 Watchlist")
        notebook.add(self.trades_tab, text="📈 Trades")

        self._build_watchlist()
        self._build_trades()

    # =====================================================
    # TABLES
    # =====================================================

    def _build_watchlist(self):
        cols = ("symbol", "strategy", "bias", "scanned_on", "status")
        self.watchlist_table = ttk.Treeview(self.watchlist_tab, columns=cols, show="headings")

        for c in cols:
            self.watchlist_table.heading(c, text=c.upper())
            self.watchlist_table.column(c, width=120, anchor="center")

        self.watchlist_table.pack(fill="both", expand=True, padx=6, pady=6)

    def _build_trades(self):
        cols = ("symbol", "entry", "ltp", "sl", "target", "qty", "pnl", "r", "progress", "status")
        self.trades_table = ttk.Treeview(self.trades_tab, columns=cols, show="headings")

        for c in cols:
            self.trades_table.heading(c, text=c.upper())
            self.trades_table.column(c, width=100, anchor="center")

        self.trades_table.pack(fill="both", expand=True, padx=6, pady=6)

        # 🎨 ROW TAGS
        self.trades_table.tag_configure("profit", foreground="green")
        self.trades_table.tag_configure("loss", foreground="red")
        self.trades_table.tag_configure("near", foreground="orange")
        self.trades_table.tag_configure("closed", foreground="gray")

    # =====================================================
    # DATA
    # =====================================================

    def refresh_data(self):
        self._load_watchlist()
        self._load_trades()

    def _load_watchlist(self):
        self.watchlist_table.delete(*self.watchlist_table.get_children())
        for r in self.watchlist_repo.fetch_all():
            self.watchlist_table.insert("", "end", values=(
                r["symbol"], r["strategy"], r["bias"], r["scanned_on"], r["status"]
            ))

    # =====================================================
    # TRADES + KPI
    # =====================================================

    def _load_trades(self):
        self.trades_table.delete(*self.trades_table.get_children())

        rows = self.trade_repo.fetch_recent_with_pnl(limit=100)

        total_pnl = 0
        win = loss = active = 0

        for r in rows:
            symbol = r["symbol"]
            entry = float(r["entry"])
            sl = float(r["sl"])
            target = float(r["target"])
            qty = int(r["qty"])
            status = r["status"]
            initial_qty = r["initial_qty"] or qty

            ltp = self._get_ltp_cached(symbol)
            risk = abs(entry - sl)

            pnl = "--"
            r_mult = "--"
            progress = "--"
            tag = ""

            if ltp and risk > 0:
                pnl_val = round((ltp - entry) * qty, 2)
                r_mult = round((ltp - entry) / risk, 2)
                progress_val = max(0, min(100, round(((ltp - entry) / (target - entry)) * 100, 1)))
                progress = f"{progress_val}%"
                pnl = pnl_val

                total_pnl += pnl_val
                active += 1

                if pnl_val > 0:
                    win += 1
                    tag = "profit"
                elif pnl_val < 0:
                    loss += 1
                    tag = "loss"

                if progress_val >= 70 and status in ("OPEN", "PARTIAL"):
                    tag = "near"

            if status == "TARGET_HIT":
                pnl = round((target - entry) * initial_qty, 2)
                r_mult = round((target - entry) / risk, 2)
                progress = "100%"
                tag = "closed"

            elif status in ("SL_HIT", "SL_CLOSE_BASED", "EMERGENCY_EXIT"):
                pnl = round((sl - entry) * initial_qty, 2)
                r_mult = -1.0
                progress = "0%"
                tag = "closed"

            self.trades_table.insert("", "end", values=(
                symbol, entry, ltp or "--", sl, target, qty, pnl, r_mult, progress, status
            ), tags=(tag,))

        # ---------- KPI UPDATE ----------
        self.kpi_labels["capital"].config(text="💰 Capital: 1,00,000")
        self.kpi_labels["active"].config(text=f"📊 Active: {active}")
        self.kpi_labels["profit"].config(text=f"🟢 Wins: {win}", foreground="green")
        self.kpi_labels["loss"].config(text=f"🔴 Loss: {loss}", foreground="red")
        self.kpi_labels["pnl"].config(
            text=f"💵 PnL: {round(total_pnl,2)}",
            foreground="green" if total_pnl >= 0 else "red"
        )

    # =====================================================
    # LTP CACHE LOGIC
    # =====================================================

    def _get_ltp_cached(self, symbol):
        now = datetime.now().time()

        after_market = now >= time(16, 30) or now <= time(8, 0)

        if after_market and symbol in self.ltp_cache:
            return self.ltp_cache[symbol][0]

        try:
            ltp = self.provider.get_ltp(symbol)
            if ltp:
                self.ltp_cache[symbol] = (ltp, datetime.now())
            return ltp
        except Exception:
            return None

    # =====================================================
    # BUTTONS
    # =====================================================

    def run_daily_scan(self):
        self._run_threaded(self.manager.tf_daily_scan, "Daily Scan Failed")

    def run_morning_confirm(self):
        self._run_threaded(lambda: self.manager.tf_morning_confirm(capital=100000), "Morning Confirm Failed")

    def run_monitor(self):
        self._run_threaded(self.manager.tf_monitor, "Monitor Failed")

    def _run_threaded(self, task, title):
        def worker():
            try:
                task()
                self.after(0, self.refresh_data)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror(title, str(e)))

        threading.Thread(target=worker, daemon=True).start()

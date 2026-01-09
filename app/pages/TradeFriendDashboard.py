import threading
import tkinter.messagebox as messagebox
from tkinter import ttk, StringVar
from datetime import datetime, time

from core.TradeFriendDataProvider import TradeFriendDataProvider
from db.TradeFriendTradeRepo import TradeFriendTradeRepo
from db.TradeFriendWatchlistRepo import TradeFriendWatchlistRepo
from utils.TradeFriendManager import TradeFriendManager
from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo
from db.TradeFriendTradeHistoryRepo import TradeFriendTradeHistoryRepo



class TradeFriendDashboard(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)

        self.watchlist_repo = TradeFriendWatchlistRepo()
        self.trade_repo = TradeFriendTradeRepo()
        self.manager = TradeFriendManager()
        self.provider = TradeFriendDataProvider()

        # 🔒 Runtime state
        self.settings_repo = TradeFriendSettingsRepo()
        self.trade_mode = self.settings_repo.get_trade_mode()

        self.trade_history_repo = TradeFriendTradeHistoryRepo()

        self.ltp_cache = {}        # {symbol: (ltp, timestamp)}

        self._build_ui()
        self.refresh_data()  # async load

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):

        # ---------- LOADING BAR ----------
        self.loading_var = StringVar(value="")
        loading_frame = ttk.Frame(self)
        loading_frame.pack(fill="x", padx=6)

        ttk.Label(
            loading_frame,
            textvariable=self.loading_var,
            foreground="blue"
        ).pack(side="left", padx=6)

        self.progress = ttk.Progressbar(
            loading_frame,
            mode="indeterminate",
            length=200
        )
        self.progress.pack(side="left", padx=6)

        # ---------- KPI HEADER ----------
        self.kpi_frame = ttk.Frame(self)
        self.kpi_frame.pack(fill="x", padx=8, pady=6)

        self.kpi_labels = {}
        for key in ["capital",  
                    "swing_used",       # locked capital
                    "swing_available",  # free swing capital 
                    "active", "profit", "loss", "pnl"]:
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

        ttk.Button(control_bar, text="📊 Daily Scan", command=self.run_daily_scan)\
            .pack(side="left", padx=5)

        ttk.Button(control_bar, text="🚀 Morning Confirm", command=self.run_morning_confirm)\
            .pack(side="left", padx=5)

        ttk.Button(control_bar, text="📈 Monitor", command=self.run_monitor)\
            .pack(side="left", padx=5)

        ttk.Button(control_bar, text="🔄 Refresh", command=self.refresh_data)\
            .pack(side="right", padx=5)

        self.mode_btn = ttk.Button(
            control_bar,
            text="📝 PAPER",
            command=self.toggle_trade_mode
        )
        self.mode_btn.pack(side="right", padx=5)

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
        cols = ("symbol", "entry", "ltp", "sl", "target", "qty",
                "pnl", "r", "progress", "status")

        self.trades_table = ttk.Treeview(
            self.trades_tab,
            columns=cols,
            show="headings"
        )

        for c in cols:
            self.trades_table.heading(c, text=c.upper())
            self.trades_table.column(c, width=100, anchor="center")

        self.trades_table.pack(fill="both", expand=True, padx=6, pady=6)

        self.trades_table.tag_configure("profit", foreground="green")
        self.trades_table.tag_configure("loss", foreground="red")
        self.trades_table.tag_configure("near", foreground="orange")
        self.trades_table.tag_configure("closed", foreground="gray")

    # =====================================================
    # DATA LOADING (ASYNC)
    # =====================================================

    def refresh_data(self):
        self._start_loading("Loading watchlist & trades...")
        threading.Thread(
            target=self._load_data_background,
            daemon=True
        ).start()

    def _load_data_background(self):
        try:
            watchlist_rows = self.watchlist_repo.fetch_all()
            active_trades = self.trade_repo.fetch_active_trades(limit=50)
            closed_trades = self.trade_history_repo.fetch_recent_closed(limit=50)

            trade_rows = list(active_trades) + list(closed_trades)

            self.after(0, lambda: self._update_watchlist_ui(watchlist_rows))
            self.after(0, lambda: self._update_trades_ui(trade_rows))
        finally:
            self.after(0, self._stop_loading)

    def _update_watchlist_ui(self, rows):
        self.watchlist_table.delete(*self.watchlist_table.get_children())
        for r in rows:
            self.watchlist_table.insert("", "end", values=(
                r["symbol"], r["strategy"], r["bias"],
                r["scanned_on"], r["status"]
            ))

    def _update_trades_ui(self, rows):
        self.trades_table.delete(*self.trades_table.get_children())

        total_pnl = 0.0
        active = win = loss = 0

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

            pnl = r_mult = progress = "--"
            tag = ""

            # ================= ACTIVE TRADES =================
            if ltp and risk > 0 and status in ("OPEN", "PARTIAL"):
                pnl_val = round((ltp - entry) * qty, 2)
                r_mult = round((ltp - entry) / risk, 2)

                if target != entry:
                    progress_val = max(
                        0,
                        min(100, round(((ltp - entry) / (target - entry)) * 100, 1))
                    )
                    progress = f"{progress_val}%"
                else:
                    progress = "--"

                pnl = pnl_val
                total_pnl += pnl_val
                active += 1

                if pnl_val > 0:
                    win += 1
                    tag = "profit"
                elif pnl_val < 0:
                    loss += 1
                    tag = "loss"

                if progress != "--" and float(progress[:-1]) >= 70:
                    tag = "near"

            # ================= CLOSED : TARGET =================
            elif status == "TARGET_HIT":
                pnl = round((target - entry) * initial_qty, 2)
                r_mult = round((target - entry) / risk, 2) if risk > 0 else "--"
                progress = "100%"
                total_pnl += pnl
                tag = "closed"

            # ================= CLOSED : SL / EXIT =================
            elif status in ("SL_HIT", "SL_CLOSE_BASED", "EMERGENCY_EXIT"):
                pnl = round((sl - entry) * initial_qty, 2)
                r_mult = -1.0
                progress = "0%"
                total_pnl += pnl
                tag = "closed"

            self.trades_table.insert(
                "",
                "end",
                values=(
                    symbol,
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
                tags=(tag,)
            )

        # ================= KPI SECTION =================

            settings = self.settings_repo.fetch()

            total_capital = settings["total_capital"] or 0
            max_swing = settings["max_swing_capital"] or 0
            available_swing = settings["available_swing_capital"] or 0
            used_swing = round(max_swing - available_swing, 2)


        # ---------------- KPI UPDATE ----------------
        self.kpi_labels["capital"].config(
            text=f"💰 Total: {round(total_capital, 2)}",
            foreground="black"
        )

        self.kpi_labels["swing_used"].config(
            text=f"🔒 Used: {used_swing}",
            foreground="orange"
        )

        self.kpi_labels["swing_available"].config(
            text=f"🟢 Free: {round(available_swing, 2)}",
            foreground="green"
        )

        self.kpi_labels["active"].config(
            text=f"📊 Active: {active}",
            foreground="black"
        )

        self.kpi_labels["profit"].config(
            text=f"🟢 Wins: {win}",
            foreground="green"
        )

        self.kpi_labels["loss"].config(
            text=f"🔴 Loss: {loss}",
            foreground="red"
        )

        self.kpi_labels["pnl"].config(
            text=f"💵 PnL: {round(total_pnl, 2)}",
            foreground="green" if total_pnl >= 0 else "red"
        )

    # =====================================================
    # LTP CACHE + MARKET GUARD
    # =====================================================

    def _get_ltp_cached(self, symbol):
        now = datetime.now()
        weekday = now.weekday()
        current_time = now.time()

        market_closed = (
            weekday in (5, 6) or
            (weekday == 4 and current_time >= time(16, 30)) or
            (weekday == 0 and current_time < time(7, 30)) or
            current_time < time(7, 30) or
            current_time >= time(21, 45)
        )

        if market_closed:
            return self.ltp_cache.get(symbol, (None,))[0]

        try:
            ltp = self.provider.get_ltp(symbol)
            if ltp:
                self.ltp_cache[symbol] = (ltp, now)
            return ltp
        except Exception:
            return None

    # =====================================================
    # TRADE MODE
    # =====================================================

    def toggle_trade_mode(self):
        self.trade_mode = "LIVE" if self.trade_mode == "PAPER" else "PAPER"

        # Persist to DB
        self.settings_repo.set_trade_mode(self.trade_mode)

        self.mode_btn.config(
            text="🟢 LIVE" if self.trade_mode == "LIVE" else "📝 PAPER"
        )

        messagebox.showinfo(
            "Trade Mode Updated",
            f"Trade mode set to: {self.trade_mode}"
        )

    # =====================================================
    # ACTION BUTTONS
    # =====================================================

    def run_daily_scan(self):
        self._run_threaded(
            lambda: self.manager.tf_daily_scan(mode=self.trade_mode),
            "Daily Scan Failed"
        )

    def run_morning_confirm(self):
        self._run_threaded(
            lambda: self.manager.tf_morning_confirm(
                capital=100000,
                mode=self.trade_mode
            ),
            "Morning Confirm Failed"
        )

    def run_monitor(self):
        self._run_threaded(
            lambda: self.manager.tf_monitor(),
            "Monitor Failed"
        )

    def _run_threaded(self, task, title):
        def worker():
            try:
                task()
                self.after(0, self.refresh_data)
            except Exception as e:
                self.after(0, lambda err=str(e): messagebox.showerror(title, err))
    
        threading.Thread(target=worker, daemon=True).start()

    # =====================================================
    # LOADING HELPERS
    # =====================================================

    def _start_loading(self, msg):
        self.loading_var.set(msg)
        self.progress.start(10)

    def _stop_loading(self):
        self.progress.stop()
        self.loading_var.set("")

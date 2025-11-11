import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox, END, LEFT, RIGHT, Y, BOTH, X, W, EW, CENTER
import logging
from db.dhan_db_helper import DhanDBHelper

order_logger = logging.getLogger("orders")
logger = logging.getLogger(__name__)

class HoldingsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.db = DhanDBHelper()
        self.active_popup = None

        # ===== Title =====
        ttk.Label(
            self,
            text="📊 Holdings",
            font=("Segoe UI", 16, "bold")
        ).pack(anchor="w", pady=10, padx=10)

        # ===== Broker Selection =====
        self.selected_broker = ttk.StringVar(value="DHAN")
        broker_frame = ttk.Frame(self)
        broker_frame.pack(fill=X, padx=10, pady=5)

        for broker in ["DHAN", "Angel", "Motilal Oswal"]:
            ttk.Radiobutton(
                broker_frame,
                text=broker,
                variable=self.selected_broker,
                value=broker,
                command=self.load_holdings,
                bootstyle="info-outline-toolbutton"
            ).pack(side=LEFT, padx=10)

        # ===== Search Box =====
        self.search_var = ttk.StringVar()
        search_entry = ttk.Entry(
            self,
            textvariable=self.search_var,
            bootstyle="info",
        )
        search_entry.pack(fill=X, padx=10, pady=(0, 10))
        search_entry.insert(0, "🔍 Search by symbol...")

        def on_focus_in(event):
            if search_entry.get() == "🔍 Search by symbol...":
                search_entry.delete(0, END)

        def on_focus_out(event):
            if not search_entry.get():
                search_entry.insert(0, "🔍 Search by symbol...")

        search_entry.bind("<FocusIn>", on_focus_in)
        search_entry.bind("<FocusOut>", on_focus_out)
        search_entry.bind("<KeyRelease>", lambda e: self.load_holdings())

        # ===== Table Container Frame =====
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=BOTH, expand=True, padx=8, pady=6)
        
        # ===== Treeview Table =====
        self.tree = ttk.Treeview(
            table_frame,
            columns=("Symbol", "Quantity", "Avg Price", "Current Price",
                     "Profit %", "Target1", "Target2", "Action"),
            show="headings",
            bootstyle="info"
        )
        
        # Set column headers and widths
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col, anchor=CENTER)
            self.tree.column(col, anchor=CENTER, width=130, stretch=False, minwidth=100)
        
        # Attach scrollbar inside same frame
        scrollbar = ttk.Scrollbar(table_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack elements with consistent alignment
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        # ===== Adaptive Theme Styling =====
        style = ttk.Style()
        theme = style.theme_use()
        
        # Adjust padding/row height for theme consistency
        if theme == "vapor":
            row_h, pad = 34, (6, 2, 6, 2)
        elif theme == "cyborg":
            row_h, pad = 32, (5, 2, 5, 2)
        else:
            row_h, pad = 30, (4, 2, 4, 2)
        
        style.configure(
            "info.Treeview",
            rowheight=row_h,
            borderwidth=0,
            padding=pad,
            font=("Segoe UI", 10)
        )
        style.configure(
            "info.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            padding=(6, 6, 6, 6)
        )
        
        # Alternate row colors (theme-safe)
        bg_primary = style.lookup("Treeview", "background") or "#1f1f1f"
        bg_secondary = style.lookup("Treeview", "fieldbackground") or "#262626"
        
        self.tree.tag_configure("evenrow", background=bg_primary)
        self.tree.tag_configure("oddrow", background=bg_secondary)
        

        # ===== Double-click Action =====
        self.tree.bind("<Double-1>", self._on_row_double_click)

        # ===== Initial Load =====
        self.load_holdings()

    # ===========================
    # Load holdings from DB
    # ===========================
    def load_holdings(self):
        try:
            if getattr(self, "active_popup", None) and self.active_popup.winfo_exists():
                return

            self.tree.delete(*self.tree.get_children())

            broker = self.selected_broker.get()
            holdings = [h for h in self.db.get_all() if h.get("broker", "Dhan") == broker]
            logger.info(f"Loading holdings for broker: {broker}, total records: {len(holdings)}")

            query = self.search_var.get().strip().lower()
            if query and query != "🔍 search by symbol...":
                holdings = [h for h in holdings if query in str(h.get("symbol", "")).lower()]

            # Theme colors and profit text colors
            style = ttk.Style()
            bg_primary = style.lookup("Treeview", "background") or "#1f1f1f"
            bg_secondary = style.lookup("Treeview", "fieldbackground") or "#262626"
            fg_profit = "#4CAF50"  # green
            fg_loss = "#E53935"    # red

            self.tree.tag_configure("evenrow", background=bg_primary)
            self.tree.tag_configure("oddrow", background=bg_secondary)
            self.tree.tag_configure("profit", foreground=fg_profit)
            self.tree.tag_configure("loss", foreground=fg_loss)

            for i, h in enumerate(holdings):
                symbol = str(h.get("symbol", "")).strip()
                sym = f"{symbol}-EQ" if symbol else "UNKNOWN"

                qty = h.get("quantity", 0)
                avg = h.get("avg_price")
                ltp = h.get("ltp")

                def safe_float(val):
                    try:
                        return float(val)
                    except (TypeError, ValueError):
                        return None

                avg_f = safe_float(avg)
                ltp_f = safe_float(ltp)

                if ltp_f is None or avg_f in (None, 0):
                    profit_pct = 0
                else:
                    profit_pct = (ltp_f - avg_f) / avg_f * 100

                t1_active = "Active" if h.get("active_target1") else "Inactive"
                t2_active = "Active" if h.get("active_target2") else "Inactive"

                row_tag = "evenrow" if i % 2 == 0 else "oddrow"
                profit_tag = "profit" if profit_pct >= 0 else "loss"

                self.tree.insert(
                    "",
                    "end",
                    values=(
                        sym,
                        qty,
                        avg_f if avg_f is not None else 0.0,
                        ltp_f if ltp_f is not None else 0.0,
                        f"{profit_pct:.2f}%",
                        t1_active,
                        t2_active,
                        "Set Target",
                    ),
                    tags=(row_tag, profit_tag),
                )

        except Exception as e:
            logger.exception("Error loading holdings")
            messagebox.showerror("Error", f"Failed to load holdings:\n{e}")

    # ===========================
    # Double-click row
    # ===========================
    def _on_row_double_click(self, event):
        try:
            item = self.tree.focus()
            if not item or not self.tree.exists(item):
                return
            row = self.tree.item(item)["values"]
            symbol = str(row[0]).replace("-EQ", "")
            record = self.db.get_by_symbol(symbol)
            if record:
                self.open_target_popup(record)
        except Exception as e:
            order_logger.error(f"Error opening target popup: {e}", exc_info=True)

    # ===========================
    # Target popup
    # ===========================
    def open_target_popup(self, record):
        if self.active_popup and self.active_popup.winfo_exists():
            self.active_popup.destroy()

        popup = ttk.Toplevel(self)
        self.active_popup = popup
        popup.title(f"Set Targets for {record['symbol']}")
        popup.geometry("520x360")
        popup.resizable(False, False)
        popup.grab_set()

        frame = ttk.Labelframe(popup, text=f"Set Targets for {record['symbol']}", bootstyle="info")
        frame.pack(fill=BOTH, expand=True, padx=15, pady=15)

        for i in range(4):
            frame.columnconfigure(i, weight=1)

        # ===== Mode =====
        ttk.Label(frame, text="Target Mode:", bootstyle="secondary").grid(row=0, column=0, padx=5, pady=5, sticky=W)
        mode_var = ttk.StringVar(value=record.get("mode", "Manual"))
        ttk.Radiobutton(frame, text="Manual", variable=mode_var, value="Manual").grid(row=0, column=1, sticky=W, padx=5)
        ttk.Radiobutton(frame, text="Auto (SR-based)", variable=mode_var, value="Auto (SR-based)").grid(row=0, column=2, sticky=W, padx=5)

        # ===== Target 1 =====
        ttk.Label(frame, text="Target 1:", bootstyle="secondary").grid(row=1, column=0, sticky=W, pady=5)
        target1_var = ttk.DoubleVar(value=record.get("target1", 0))
        qty1_var = ttk.IntVar(value=record.get("sell_qty_target1", 0))
        active1_var = ttk.BooleanVar(value=bool(record.get("active_target1", 1)))

        ttk.Entry(frame, textvariable=target1_var, width=10).grid(row=1, column=1, sticky=W, padx=5)
        ttk.Entry(frame, textvariable=qty1_var, width=8).grid(row=1, column=2, sticky=W, padx=5)
        ttk.Checkbutton(frame, text="Active", variable=active1_var, bootstyle="success-round-toggle").grid(row=1, column=3, sticky=W)

        # ===== Target 2 =====
        ttk.Label(frame, text="Target 2:", bootstyle="secondary").grid(row=2, column=0, sticky=W, pady=5)
        target2_var = ttk.DoubleVar(value=record.get("target2", 0))
        qty2_var = ttk.IntVar(value=record.get("sell_qty_target2", 0))
        active2_var = ttk.BooleanVar(value=bool(record.get("active_target2", 1)))

        ttk.Entry(frame, textvariable=target2_var, width=10).grid(row=2, column=1, sticky=W, padx=5)
        ttk.Entry(frame, textvariable=qty2_var, width=8).grid(row=2, column=2, sticky=W, padx=5)
        ttk.Checkbutton(frame, text="Active", variable=active2_var, bootstyle="success-round-toggle").grid(row=2, column=3, sticky=W)

        # ===== Save Button =====
        def save_targets():
            try:
                self.db.insert_or_update({
                    "symbol": record["symbol"],
                    "broker": record.get("broker", "Dhan"),
                    "quantity": record.get("quantity", 0),
                    "avg_price": record.get("avg_price", 0.0),
                    "ltp": record.get("ltp", 0.0),
                    "target1": float(target1_var.get()),
                    "sell_qty_target1": int(qty1_var.get()),
                    "active_target1": 1 if active1_var.get() else 0,
                    "target2": float(target2_var.get()),
                    "sell_qty_target2": int(qty2_var.get()),
                    "active_target2": 1 if active2_var.get() else 0,
                    "mode": mode_var.get(),
                    "monitor_target1": record.get("monitor_target1", 1),
                    "monitor_target2": record.get("monitor_target2", 1),
                })
                order_logger.info(f"Targets updated for {record['symbol']}")
                if popup.winfo_exists():
                    popup.destroy()
                self.load_holdings()
            except Exception as e:
                order_logger.error(f"Error saving targets: {e}", exc_info=True)
                messagebox.showerror("Error", f"Failed to save targets: {e}")

        ttk.Button(frame, text="Save", bootstyle="success", command=save_targets).grid(
            row=3, column=0, columnspan=4, pady=20, sticky=EW
        )

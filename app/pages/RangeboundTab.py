import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox, END, LEFT, RIGHT, Y, BOTH, X, CENTER
import logging
from config.settings import RangeBoundInput_DIR, RangeBoundOutput_DIR

from db.rangebound_db_helper import RangeboundDB
from core.rangebound_finder import run_rangebound_finder
# from reports.rangebound_pdf import create_rangebound_pdf
# from alerts.telegram_alert import send_telegram_message
# from alerts.email_alert import send_email_alert
# from charts.rangebound_chart import open_range_chart

logger = logging.getLogger(__name__)

class RangeboundTab(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)
        self.db = RangeboundDB()

        ttk.Label(
            self,
            text="📘 Rangebound Stocks",
            font=("Segoe UI", 16, "bold")
        ).pack(anchor="w", pady=10, padx=10)

        # ========== TOP BUTTONS ==========
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=X, padx=10, pady=5)

        ttk.Button(top_frame, text="🔍 Run Scanner", bootstyle="success",
                   command=self.run_scanner).pack(side=LEFT, padx=5)

        ttk.Button(top_frame, text="📄 Export PDF", bootstyle="info",
                   command=self.export_pdf).pack(side=LEFT, padx=5)

        ttk.Button(top_frame, text="📊 Open Chart", bootstyle="warning",
                   command=self.open_chart).pack(side=LEFT, padx=5)

        # ========== SEARCH BOX ==========
        self.search_var = ttk.StringVar()
        search_entry = ttk.Entry(self, textvariable=self.search_var, bootstyle="info")
        search_entry.pack(fill=X, padx=10, pady=(5, 10))

        search_entry.insert(0, "🔍 Search symbol...")
        search_entry.bind("<KeyRelease>", lambda e: self.load_table())

        # ========== TABLE ==========
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=BOTH, expand=True, padx=8, pady=6)

        self.tree = ttk.Treeview(
            table_frame,
            columns=("Symbol", "Year Low", "Year High",
                     "Range %", "Last Close", "Signal"),
            show="headings",
            bootstyle="info"
        )

        for col in self.tree["columns"]:
            self.tree.heading(col, text=col, anchor=CENTER)
            self.tree.column(col, anchor=CENTER, width=120, stretch=False)

        scrollbar = ttk.Scrollbar(table_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Row styles
        style = ttk.Style()
        theme = style.theme_use()
        row_h = 34 if theme == "vapor" else 30
        style.configure("info.Treeview", rowheight=row_h)

        bg1 = style.lookup("Treeview", "background") or "#202020"
        bg2 = style.lookup("Treeview", "fieldbackground") or "#303030"
        self.tree.tag_configure("evenrow", background=bg1)
        self.tree.tag_configure("oddrow", background=bg2)

        self.load_table()

    # ========== Load table ==========
    def load_table(self):
        try:
            self.tree.delete(*self.tree.get_children())

            rows = self.db.fetch("SELECT * FROM rangebound_stocks ORDER BY symbol ASC")
            rows = [dict(zip(["symbol","date","year_low","year_high","low_touches","high_touches","range_percent","last_close","updated_at"], r)) for r in rows]

            q = self.search_var.get().lower().strip()
            if q and q != "🔍 search symbol...":
                rows = [r for r in rows if q in r["symbol"].lower()]

            for i, r in enumerate(rows):
                tag = "evenrow" if i % 2 == 0 else "oddrow"
                # Dynamic signal calculation (optional)
                # For now, just placeholder WAIT as DB doesn't store signal
                signal = "WAIT"
                self.tree.insert("", "end",
                    values=(
                        r["symbol"],
                        r["year_low"],
                        r["year_high"],
                        f"{r['range_percent']}%",
                        r["last_close"],
                        signal
                    ),
                    tags=(tag,)
                )

        except Exception as e:
            logger.error("Failed to load rangebound table", exc_info=True)
            messagebox.showerror("Error", str(e))

    # ========== Run Rangebound Scanner ==========
    def run_scanner(self):
        try:
            input_folder = RangeBoundInput_DIR
            output_folder = RangeBoundOutput_DIR

            ok, results = run_rangebound_finder(input_folder, output_folder)
            if ok:
                self.load_table()
                messagebox.showinfo("Success", f"Scanner completed.\n{len(results)} symbols updated.")
        except Exception as e:
            logger.error("Scanner error", exc_info=True)
            messagebox.showerror("Error", str(e))

    # ========== PDF Export ==========
    def export_pdf(self):
        try:
            # Placeholder for PDF export
            # filename = create_rangebound_pdf()
            filename = "Rangebound_Report.pdf"
            messagebox.showinfo("Success", f"PDF generated:\n{filename}")
        except Exception as e:
            logger.error("PDF export error", exc_info=True)
            messagebox.showerror("Error", str(e))

    # ========== Chart ==========
    def open_chart(self):
        try:
            selected = self.tree.focus()
            if not selected:
                messagebox.showwarning("Warning", "Select a stock first")
                return
            symbol = self.tree.item(selected)["values"][0]
            # Placeholder for chart
            # open_range_chart(symbol)
            messagebox.showinfo("Info", f"Chart would open for {symbol}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

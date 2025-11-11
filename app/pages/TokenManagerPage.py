import os
import json
import logging
import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as tb
from config.settings import NSE_EQTY_FILE
from db.missing_token_db import MissingTokenDB
from utils.instrumenthelper import InstrumentHelper
from utils.symbol_resolver import SymbolResolver

logger = logging.getLogger(__name__)

class TokenManagerPage(tb.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent

        # DB & Helper
        self.db = MissingTokenDB()
        self.helper = InstrumentHelper()

        # Memory cache
        self.all_tokens = self.db.get_all() or []  # list of all tokens
        self.token_vars = {}  # checkbox variables keyed by symbol

        # --- Search Frame ---
        search_frame = tb.Frame(self)
        search_frame.pack(fill="x", pady=5, padx=10)

        tb.Label(search_frame, text="Search Symbol:", font=("Arial", 12, "bold")).pack(side="left", padx=(5,5))

        self.search_var = tk.StringVar()
        self.search_entry = tb.Entry(search_frame, textvariable=self.search_var, width=25)
        self.search_entry.pack(side="left", padx=(0,5))
        self.search_entry.bind("<KeyRelease>", self.on_keyrelease)

        # Autocomplete listbox
        self.lb_autocomplete = tk.Listbox(search_frame, height=5)
        self.lb_autocomplete.bind("<<ListboxSelect>>", self.on_listbox_select)

        # Radio buttons
        self.filter_var = tk.StringVar(value="active")
        tb.Radiobutton(search_frame, text="Active", variable=self.filter_var, value="active",
                       bootstyle="success", command=self.refresh_table).pack(side="left", padx=5)
        tb.Radiobutton(search_frame, text="Inactive", variable=self.filter_var, value="inactive",
                       bootstyle="danger", command=self.refresh_table).pack(side="left", padx=5)
        tb.Radiobutton(search_frame, text="All", variable=self.filter_var, value="all",
                       bootstyle="secondary", command=self.refresh_table).pack(side="left", padx=5)

        # --- Scrollable Table ---
        self.setup_table()
        self.refresh_table()

    # ---------------- Setup Table ----------------
    def setup_table(self):
        self.table_container = tb.Frame(self)
        self.table_container.pack(fill="both", expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(self.table_container, borderwidth=0)
        self.scrollbar = tb.Scrollbar(self.table_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tb.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0,0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    # ---------------- Refresh Table ----------------
    def refresh_table(self):
        for w in self.scrollable_frame.winfo_children():
            w.destroy()

        query = self.search_var.get().lower().strip()
        tokens = self.all_tokens.copy()

        # Apply search filter
        if query:
            tokens = [t for t in tokens if query in t.get("symbol","").lower()]

        # Apply active/inactive filter
        f = self.filter_var.get()
        if f == "active":
            tokens = [t for t in tokens if t.get("active",1)==1]
        elif f == "inactive":
            tokens = [t for t in tokens if t.get("active",1)==0]

        # Headers
        headers = ["Symbol", "Name", "Active", "Resolve", "Toggle"]
        for col, text in enumerate(headers):
            tb.Label(self.scrollable_frame, text=text, font=("Arial", 12, "bold")).grid(row=0, column=col, padx=5, pady=5)

        # Populate rows
        for r, token in enumerate(tokens, start=1):
            symbol = token.get("symbol","")
            name = token.get("name","")
            active = token.get("active",1)

            tb.Label(self.scrollable_frame, text=symbol).grid(row=r,column=0,padx=5,pady=3)
            tb.Label(self.scrollable_frame, text=name).grid(row=r,column=1,padx=5,pady=3)

            var = self.token_vars.get(symbol, tk.IntVar(value=active))
            chk = tb.Checkbutton(self.scrollable_frame, variable=var,
                                 bootstyle="success" if var.get() else "secondary",
                                 command=lambda sym=symbol, var=var: self.toggle_active_status(sym, var))
            chk.grid(row=r,column=2,padx=5,pady=3)
            self.token_vars[symbol] = var

            # Resolve button
            btn_resolve = tb.Button(self.scrollable_frame, text="Resolve", bootstyle="info",
                                    width=10, command=lambda sym=symbol: self.resolve_token(sym))
            btn_resolve.grid(row=r,column=3,padx=5,pady=3)

            # Toggle button
            btn_toggle = tb.Button(self.scrollable_frame, text="Toggle", bootstyle="warning",
                                   width=10, command=lambda sym=symbol: self.toggle_active(sym))
            btn_toggle.grid(row=r,column=4,padx=5,pady=3)

    # ---------------- Toggle Active ----------------
    def toggle_active_status(self, symbol, var):
        new_val = var.get()
        # Update in-memory cache
        for token in self.all_tokens:
            if token.get("symbol") == symbol:
                token["active"] = new_val
                break
        # Update DB
        self.db.update_active_status(symbol=symbol, name=symbol, active=new_val)
        self.refresh_table()
        logger.info(f"{symbol} active status updated to {new_val}")

    def toggle_active(self, symbol):
        var = self.token_vars[symbol]
        var.set(0 if var.get() else 1)
        self.toggle_active_status(symbol, var)

    # ---------------- Resolve Token ----------------
    def resolve_token(self, symbol):
        try:
            search_name = symbol.replace("-EQ","")
            result = self.helper.search_symbol("NSE", search_name)
            extracted_list = SymbolResolver.extract_symbol_objects(result)
            if not extracted_list:
                messagebox.showerror("Error", f"No valid entries found for {symbol}.")
                return

            preview_msg = "\n".join([str(d) for d in extracted_list])
            if not messagebox.askyesno("Preview Data", f"Data found for {symbol}:\n\n{preview_msg}\n\nSave to JSON & DB?"):
                return

            os.makedirs(os.path.dirname(NSE_EQTY_FILE) or ".", exist_ok=True)
            existing_data = []
            if os.path.exists(NSE_EQTY_FILE):
                with open(NSE_EQTY_FILE,"r") as f:
                    existing_data = json.load(f)
            existing_data.extend(extracted_list)
            with open(NSE_EQTY_FILE,"w") as f:
                json.dump(existing_data, f, indent=4)

            # Update in-memory cache & DB
            for token in self.all_tokens:
                if token.get("symbol") == symbol:
                    token["active"] = 0
                    break
            self.db.update_active_status(symbol=symbol, name=symbol, active=0)

            messagebox.showinfo("Success", f"Data for {symbol} saved to JSON & DB.")
            self.refresh_table()

        except Exception as e:
            logger.exception(f"Error resolving token {symbol}: {e}")
            messagebox.showerror("Error", f"Error resolving token {symbol}: {e}")

    # ---------------- Autocomplete ----------------
    def on_keyrelease(self, event):
        value = self.search_var.get().lower()
        if not value:
            self.lb_autocomplete.place_forget()
            self.refresh_table()
            return

        all_symbols = [t["symbol"] for t in self.all_tokens]
        suggestions = [s for s in all_symbols if value in s.lower()]

        if suggestions:
            self.lb_autocomplete.delete(0, tk.END)
            for s in suggestions:
                self.lb_autocomplete.insert(tk.END, s)
            # Safe placement
            self.lb_autocomplete.place(
                x=self.search_entry.winfo_x(),
                y=self.search_entry.winfo_y() + self.search_entry.winfo_height(),
                width=self.search_entry.winfo_width()
            )
        else:
            self.lb_autocomplete.place_forget()

        self.refresh_table()

    def on_listbox_select(self, event):
        if not self.lb_autocomplete.curselection():
            return
        index = self.lb_autocomplete.curselection()[0]
        value = self.lb_autocomplete.get(index)
        self.search_var.set(value)
        self.lb_autocomplete.place_forget()
        self.refresh_table()

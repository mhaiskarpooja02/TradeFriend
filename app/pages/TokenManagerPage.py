import os
import json
import logging
import random
import time
import tkinter as tk
from tkinter import messagebox
import csv
from tkinter import filedialog
import ttkbootstrap as tb
from config.settings import NSE_EQTY_FILE
from db.missing_token_db import MissingTokenDB
from utils.instrumenthelper import InstrumentHelper
from utils.symbol_resolver import SymbolResolver
from brokers.angel_client import AngelClient
from datetime import datetime
import pandas as pd
from config.TradeFriendConfig import SEARCH_DELAY
from db.tradefindinstrument_db import TradeFindDB
logger = logging.getLogger(__name__)

class TokenManagerPage(tb.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent

        # DB & Helper
        self.db = MissingTokenDB()
        self.helper = InstrumentHelper()
        self.dbinstrument = TradeFindDB()

        self.db.cleanup_invalid_symbols()

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

        tb.Button(
    search_frame,
    text="Validate & Export Tokens",
    bootstyle="primary",
    command=self.validate_tokens_with_history
    ).pack(side="left", padx=10)
        
        tb.Button(
    search_frame,
    text="Resolve All Tokens",
    bootstyle="primary",
    command=self.resolve_alltokens
    ).pack(side="left", padx=10)

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

            for item in extracted_list:
                trading_symbol = item.get("symbol")
                token = item.get("token")

                self.dbinstrument.upsert_symbol(
                          symbol=symbol,
                          trading_symbol=trading_symbol,
                          token=str(token)
                      )

            messagebox.showinfo("Success", f"Data for {symbol} saved to JSON & DB.")
            self.refresh_table()

        except Exception as e:
            logger.exception(f"Error resolving token {symbol}: {e}")
            messagebox.showerror("Error", f"Error resolving token {symbol}: {e}")

    # ---------------- Resolve Token ----------------
    def resolve_alltokens(self):
      try:
          allsymbols = self.all_tokens.copy()

          # Always enforce active = 1
          symbols = [s for s in allsymbols if s.get("active", 1) == 1]

          if not symbols:
              messagebox.showwarning("No Symbols", "No symbols to process.")
              return

          active_count = len(symbols)
          logger.info(f"Active symbols count: {active_count}")

          for item in symbols:
              symbol = item.get("symbol")

              try:
                  search_name = symbol.replace("-EQ", "")
                  result = self.helper.search_symbol("NSE", search_name)

                  extracted_list = SymbolResolver.extract_symbol_objects(result)

                  if not extracted_list:
                    #   messagebox.showerror(
                    #       "Error", f"No valid entries found for {symbol}."
                    #   )
                      continue   # ✅ move to next symbol

                  preview_msg = "\n".join([str(d) for d in extracted_list])
                  if not messagebox.askyesno(
                      "Preview Data",
                      f"Data found for {symbol}:\n\n{preview_msg}\n\nSave to JSON & DB?"
                  ):
                      continue   # ✅ user skipped

                  os.makedirs(os.path.dirname(NSE_EQTY_FILE) or ".", exist_ok=True)

                  existing_data = []
                  if os.path.exists(NSE_EQTY_FILE):
                      with open(NSE_EQTY_FILE, "r") as f:
                          existing_data = json.load(f)

                  existing_data.extend(extracted_list)

                  with open(NSE_EQTY_FILE, "w") as f:
                      json.dump(existing_data, f, indent=4)

                  # Update in-memory cache & DB
                  for token in self.all_tokens:
                      if token.get("symbol") == symbol:
                          token["active"] = 0
                          break

                  self.db.update_active_status(
                      symbol=symbol, name=symbol, active=0
                  )

                  

              except Exception as inner_e:
                  logger.exception(f"Error processing symbol {symbol}: {inner_e}")
                  messagebox.showerror(
                      "Error", f"Error processing {symbol}: {inner_e}"
                  )
                  continue   # ✅ continue loop even after error

      except Exception as e:
          logger.exception(f"Fatal error in resolve_alltokens: {e}")
          messagebox.showerror("Error", f"Fatal error: {e}")

      self.refresh_table()

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

    def export_valid_csv(self, data):
         # Create unique default filename
        today_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"TradeFriend_Histdattok_{today_str}.csv"

        file_path = filedialog.asksaveasfilename(
            title="Save Valid Tokens",
            defaultextension=".csv",
            initialfile=default_filename,
            filetypes=[("CSV Files", "*.csv")]
        )

        if not file_path:
            return

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["symbol", "token", "symbolName"]
            )
            writer.writeheader()
            writer.writerows(data)

        messagebox.showinfo("Success", f"CSV saved successfully:\n{file_path}")

    # def validate_tokens_with_history(self):
    #     MIN_ROWS = 2   # or 5 / 10 depending on your logic
    #     try:
    #         allsymbols = self.all_tokens.copy()

    #         # -------------------------------------------------
    #         # ✅ STEP 1: Normalize symbols safely
    #         # -------------------------------------------------
    #         symbols = []

    #         for s in allsymbols:
    #             try:
    #                 # Case 1: string
    #                 if isinstance(s, str):
    #                     if s.strip():
    #                         symbols.append(s.strip())
    #                     continue

    #                 # Case 2: sqlite3.Row
    #                 if not isinstance(s, dict):
    #                     active = s["active"] if "active" in s.keys() else 1
    #                     if active != 1:
    #                         continue

    #                     symbol = s["symbol"]
    #                     if isinstance(symbol, str) and symbol.strip():
    #                         symbols.append(symbol.strip())
    #                     continue

    #                 # Case 3: dict
    #                 active = s.get("active", 1)
    #                 if active != 1:
    #                     continue

    #                 symbol = s.get("symbol")
    #                 if isinstance(symbol, str) and symbol.strip():
    #                     symbols.append(symbol.strip())

    #             except Exception:
    #                 continue

    #         if not symbols:
    #             messagebox.showwarning("No Symbols", "No symbols to process.")
    #             return

    #         logger.info(f"Active symbols count: {len(symbols)}")

    #         # -------------------------------------------------
    #         # ✅ STEP 2: Broker Login
    #         # -------------------------------------------------
    #         broker = AngelClient()
    #         if getattr(broker, "smart_api", None) is None:
    #             logger.error("Broker login failed.")
    #             return

    #         valid_data = []
    #         failed = []

    #         # -------------------------------------------------
    #         # 🔁 STEP 3: Validate symbols
    #         # -------------------------------------------------
    #         for symbol in symbols:
    #             try:
    #                 time.sleep(SEARCH_DELAY + random.uniform(0, 0.2))

    #                 search_name = symbol.replace("-EQ", "")
    #                 result = self.helper.search_symbol("NSE", search_name)

    #                 if not result or not isinstance(result, dict) or not result.get("data"):
    #                     failed.append(f"{symbol} → Search returned empty")
    #                     continue
   
    #                 for r in result["data"]:
    #                     trading_symbol = r.get("tradingsymbol")
    #                     token = r.get("symboltoken")

    #                     if not trading_symbol or not token:
    #                         continue

    #                     # -------------------------------------------------
    #                     # 2️⃣ HISTORICAL DATA CHECK
    #                     # -------------------------------------------------


    #                     df = broker.get_historical_data(trading_symbol, token)

    #                     logger.info("%s → df object id=%s, initial shape=%s",trading_symbol, id(df), df.shape)

    #                     if df is None or df.empty:
    #                         failed.append(f"{trading_symbol} → No historical data")
    #                         continue

    #                     df = df.copy()

    #                     required_cols = ["close", "open", "high", "low", "volume"]
    #                     for col in required_cols:
    #                         if col in df.columns:
    #                             df[col] = pd.to_numeric(df[col], errors="coerce")

    #                     if "close" not in df.columns:
    #                         failed.append(f"{trading_symbol} → Missing close column")
    #                         continue

    #                     df = df.dropna(subset=["close"])

    #                     logger.info("%s → rows after numeric cleanup=%d", trading_symbol, len(df))

    #                     # ✅ ROW COUNT CHECK (this filters CONNPLEX-ST)
    #                     row_count = len(df)

    #                     if row_count < MIN_ROWS:

    #                         logger.info("%s → REJECTED (rows=%d, MIN_ROWS=%d)",trading_symbol, row_count, MIN_ROWS)
    #                         failed.append(
    #                             f"{trading_symbol} → Insufficient data points ({row_count})"
    #                         )
    #                         continue

    #                     logger.info("%s → PASSED row-count validation (rows=%d)",trading_symbol, row_count)

    #                     if len(df) <= 1:
    #                         failed.append(f"{trading_symbol} → Insufficient data points")
    #                         continue

    #                     logger.info("Final valid symbols:")
    #                     # ✅ VALID SYMBOL
    #                     valid_data.append({
    #                         "symbol": trading_symbol,
    #                         "token": str(token),
    #                         "symbolName": trading_symbol.split("-")[0]
    #                     })

    #             except Exception as e:
    #                 failed.append(f"{symbol} → {str(e)}")

    #         # -------------------------------------------------
    #         # ✅ STEP 4: Export result
    #         # -------------------------------------------------
    #         if not valid_data:
    #             messagebox.showinfo("Result", "No valid symbols found.")
    #             return

    #         self.export_valid_csv(valid_data)

    #         messagebox.showinfo(
    #             "Completed",
    #             f"Valid: {len(valid_data)}\nFailed: {len(failed)}"
    #         )

    #     except Exception as e:
    #         logger.exception("Validation failed")
    #         messagebox.showerror("Error", str(e))

    def validate_tokens_with_history(self):
        MIN_ROWS = 2
        SERIES_PRIORITY = ["-SM", "-EQ", "-SL", "-SQ", "-ST"]
    
        try:
            allsymbols = self.all_tokens.copy()
    
            # -------------------------------------------------
            # ✅ STEP 1: Normalize symbols
            # -------------------------------------------------
            symbols = []
    
            for s in allsymbols:
                try:
                    # Case 1: string
                    if isinstance(s, str):
                        if s.strip():
                            symbols.append(s.strip())
                        continue
                    
                    # Case 2: sqlite3.Row
                    if not isinstance(s, dict):
                        active = s["active"] if "active" in s.keys() else 1
                        if active != 1:
                            continue
                        
                        symbol = s["symbol"]
                        if isinstance(symbol, str) and symbol.strip():
                            symbols.append(symbol.strip())
                        continue
                    
                    # Case 3: dict
                    active = s.get("active", 1)
                    if active != 1:
                        continue
                    
                    symbol = s.get("symbol")
                    if isinstance(symbol, str) and symbol.strip():
                        symbols.append(symbol.strip())
    
                except Exception:
                    continue
                
            if not symbols:
                messagebox.showwarning("No Symbols", "No symbols to process.")
                return
    
            logger.info("Active symbols count: %d", len(symbols))
    
            # -------------------------------------------------
            # ✅ STEP 2: Broker Login
            # -------------------------------------------------
            broker = AngelClient()
            if getattr(broker, "smart_api", None) is None:
                logger.error("Broker login failed.")
                return
    
            valid_data = []
            failed = []
    
            # -------------------------------------------------
            # 🔁 STEP 3: Validate symbols
            # -------------------------------------------------
            for symbol in symbols:
                try:
                    time.sleep(SEARCH_DELAY + random.uniform(0, 0.2))
    
                    search_name = symbol.replace("-EQ", "")
                    result = self.helper.search_symbol("NSE", search_name)
    
                    if not result or not isinstance(result, dict) or not result.get("data"):
                        failed.append(f"{symbol} → Search returned empty")
                        continue
                    
                    data = result["data"]
    
                    # -------------------------------------------------
                    # 🔢 Sort series by priority (SM first, ST last)
                    # -------------------------------------------------
                    def series_rank(ts):
                        for i, suffix in enumerate(SERIES_PRIORITY):
                            if ts.endswith(suffix):
                                return i
                        return len(SERIES_PRIORITY)
    
                    data = sorted(
                        data,
                        key=lambda x: series_rank(x.get("tradingsymbol", ""))
                    )
    
                    selected = False
    
                    # -------------------------------------------------
                    # 🔍 Try each series ONE BY ONE
                    # -------------------------------------------------
                    for r in data:
                        trading_symbol = r.get("tradingsymbol")
                        token = r.get("symboltoken")
    
                        if not trading_symbol or not token:
                            continue
                        
                        logger.info(
                            "%s → trying series %s",
                            search_name, trading_symbol
                        )
    
                        df = broker.get_historical_data(trading_symbol, token)
    
                        if df is None or df.empty:
                            logger.info("%s → no historical data", trading_symbol)
                            continue
                        
                        df = df.copy(deep=True)
    
                        logger.info(
                            "%s → df id=%s, shape=%s",
                            trading_symbol, id(df), df.shape
                        )
    
                        required_cols = ["close", "open", "high", "low", "volume"]
                        for col in required_cols:
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col], errors="coerce")
    
                        if "close" not in df.columns:
                            logger.info("%s → missing close column", trading_symbol)
                            continue
                        
                        df = df.dropna(subset=["close"])
                        df = df[df["close"] > 0]
    
                        logger.info(
                            "%s → rows after cleanup=%d",
                            trading_symbol, len(df)
                        )
    
                        if "close" in df.columns:
                            logger.info(
                                "%s → close stats: count=%d, unique=%d, min=%s, max=%s",
                                trading_symbol,
                                df["close"].count(),
                                df["close"].nunique(),
                                df["close"].min(),
                                df["close"].max()
                            )
    
                        row_count = len(df)
    
                        if row_count < MIN_ROWS:
                            logger.info(
                                "%s → rejected (rows=%d, MIN_ROWS=%d)",
                                trading_symbol, row_count, MIN_ROWS
                            )
                            continue
                        
                        # -------------------------------------------------
                        # ✅ FIRST VALID SERIES FOUND → STOP
                        # -------------------------------------------------
                        logger.info(
                            "%s → SELECTED series %s (rows=%d)",
                            search_name, trading_symbol, row_count
                        )
    
                        valid_data.append({
                            "symbol": trading_symbol,
                            "token": str(token),
                            "symbolName": search_name
                        })
    
                        selected = True
                        break
                    
                    if not selected:
                        failed.append(f"{symbol} → No valid series found")
    
                except Exception as e:
                    logger.exception("%s → Validation error", symbol)
                    failed.append(f"{symbol} → {str(e)}")
    
            # -------------------------------------------------
            # ✅ STEP 4: Export result
            # -------------------------------------------------
            if not valid_data:
                messagebox.showinfo("Result", "No valid symbols found.")
                return
    
            logger.info("Final valid symbols:")
            for v in valid_data:
                logger.info("CSV → %s", v["symbol"])
    
            self.export_valid_csv(valid_data)
    
            messagebox.showinfo(
                "Completed",
                f"Valid: {len(valid_data)}\nFailed: {len(failed)}"
            )
    
        except Exception as e:
            logger.exception("Validation failed")
            messagebox.showerror("Error", str(e))
    
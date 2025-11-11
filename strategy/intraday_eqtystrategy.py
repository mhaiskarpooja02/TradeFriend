# # ========================
# # 3. main_app.py
# # ========================
# import datetime
# import pandas as pd
# from datetime import timedelta
# import json
# import threading
# import time
# import pyotp
# import customtkinter as ctk
# import tkinter as tk
# from tkinter import ttk, messagebox 

# # --- Import SmartAPI & Local Modules ---
# from SmartApi import SmartConnect # REST API for login/history
# from SmartApi.smartWebSocketV2 import SmartWebSocketV2 # WebSocket for real-time
# from utils.logger import get_logger
# from utils.symbol_resolver import SymbolResolver
# from config import API_KEY, CLIENT_CODE, PASSWORD, TOTP_SECRET, TOKEN_MAP

# logger = get_logger(__name__)

# # ----------------------------------------------------------------------
# # 1. Strategy Class: Handles Logic, History, and Streaming
# # ----------------------------------------------------------------------

# class IntradayEqtyStrategy:
#     def __init__(self, angel_client_instance):
#         self.angel_client = angel_client_instance 
#         self.ws = None
#         self.pivot_cache = {}       # {symbol: (high, low)}
#         self.candle_data = {}       # {token: {'open', 'high', 'low', 'close', 'start_time'}}
#         self.is_streaming = False
#         self.logger = logger

#     # ---------------- Initial Data Fetch (REST API) ----------------
#     def fetch_historical_data(self, token, interval="ONE_DAY", num_days=2):
#         """Fetches historical OHLC data for pivot calculation."""
#         to_date = datetime.datetime.now().date()
#         from_date = to_date - timedelta(days=num_days) 
        
#         historicParam = {
#             "exchange": "NSE",
#             "symboltoken": str(token),
#             "interval": interval,
#             "fromdate": from_date.strftime("%Y-%m-%d 09:15"),
#             "todate": to_date.strftime("%Y-%m-%d 15:30")
#         }

#         try:
#             api_response = self.angel_client.getCandleData(historicParam) 
            
#             if api_response and api_response.get('data'):
#                 data = api_response['data']
#                 columns = ['DateTime', 'Open', 'High', 'Low', 'Close', 'Volume']
#                 df = pd.DataFrame(data, columns=columns)
#                 df['DateTime'] = pd.to_datetime(df['DateTime'])
#                 df.set_index('DateTime', inplace=True)
#                 return df
#             else:
#                 self.logger.warning(f"No historical data returned from API for token {token}")
#                 return pd.DataFrame()
#         except Exception as e:
#             self.logger.error(f"Failed to fetch historical data for {token}: {e}")
#             return pd.DataFrame()
            
#     def initialize_pivot_for_token(self, symbol, token):
#         """Fetches data, calculates pivot, and caches it."""
#         prev_df = self.fetch_historical_data(token, interval="ONE_DAY", num_days=2) 
#         return self._calculate_pivot_levels(symbol, prev_df)
    
#     def _calculate_pivot_levels(self, symbol, prev_df):
#         """Calculates and caches the previous day's high and low."""
#         if prev_df.empty:
#             return None, None
        
#         # Take the H/L of the most recently closed daily candle
#         last_full_candle = prev_df.iloc[-1]
        
#         high = last_full_candle['High']
#         low = last_full_candle['Low']
        
#         self.pivot_cache[symbol] = (high, low)
#         self.logger.info(f"Pivot calculated for {symbol}: High={high:.2f}, Low={low:.2f}")
#         return high, low

#     def get_pivot(self, symbol):
#         """Retrieves the pre-calculated pivot levels by symbol."""
#         return self.pivot_cache.get(symbol, (None, None))

#     # ---------------- Candle Aggregation ----------------
#     def update_candle(self, token, ltp, interval_min=5):
#         """Updates the current X-minute candle with a new tick."""
#         now = datetime.datetime.now()
#         start_minute = (now.minute // interval_min) * interval_min
#         candle_start = now.replace(minute=start_minute, second=0, microsecond=0, day=now.day)

#         candle = self.candle_data.get(token)
#         if not candle or candle['start_time'] != candle_start:
#             if candle:
#                 # Optionally, log the closed candle here
#                 pass
#             candle = {'open': ltp, 'high': ltp, 'low': ltp, 'close': ltp, 'start_time': candle_start}
#             self.candle_data[token] = candle
#         else:
#             candle['close'] = ltp
#             candle['high'] = max(candle['high'], ltp)
#             candle['low'] = min(candle['low'], ltp)

#         return candle

#     # ---------------- Real-Time Streaming (WebSocket) ----------------
#     def start_websocket(self, token_list, tick_callback, auth_details):
#         """Starts the real-time WebSocket stream."""
#         if self.is_streaming:
#             self.logger.warning("WebSocket is already streaming.")
#             return

#         self.ws = SmartWebSocketV2(
#             auth_details["jwtToken"], 
#             auth_details["apiKey"], 
#             auth_details["clientCode"], 
#             auth_details["feedToken"]
#         )

#         def on_open(wsapp):
#             self.logger.info("WebSocket connected. Subscribing tokens...")
#             # Subscribe to LTP (mode 1)
#             self.ws.subscribe("intraday_ws", 1, token_list) 
#             self.is_streaming = True

#         self.ws.on_open = on_open
#         self.ws.on_message = lambda ws, msg: tick_callback(json.loads(msg)) 
#         self.ws.on_error = lambda ws, err: self.logger.error("WS Error: %s", err)
#         self.ws.on_close = lambda ws: (self.logger.info("WS closed."), self.__setattr__('is_streaming', False))
        
#         # Run WebSocket in a separate thread to prevent UI freezing
#         threading.Thread(target=self.ws.connect, daemon=True).start()

#     def stop_websocket(self):
#         """Closes the WebSocket connection."""
#         if self.ws and self.is_streaming:
#             self.ws.close_connection()
#             self.ws = None
#             self.is_streaming = False
#             self.logger.info("WebSocket stopped.")
#         else:
#             self.logger.warning("WebSocket is not active.")


# # ----------------------------------------------------------------------
# # 2. UI Class: Handles Authentication and Display
# # ----------------------------------------------------------------------

# class IntradayWatchlistTab(ctk.CTkFrame):
#     def __init__(self, parent):
#         super().__init__(parent)
#         self.angel_client = None
#         self.auth_details = {}  # To store JWT and Feed tokens
#         self.strategy = None
#         self.resolver = SymbolResolver(token_map=TOKEN_MAP)
#         self.watchlist = []  # List of dicts: {"symbol": str, "token": int}
        
#         self.build_ui()
#         self.authenticate_client() # Attempt login on startup

#     def authenticate_client(self):
#         """Performs login and gets necessary tokens (synchronous)."""
#         self.auth_label.configure(text="Logging in...", text_color="yellow")
#         self.update_idletasks()
        
#         try:
#             # Generate TOTP
#             totp = pyotp.TOTP(TOTP_SECRET)
#             otp = totp.now()

#             # 1. Initialize SmartConnect
#             self.angel_client = SmartConnect(api_key=API_KEY)

#             # 2. Generate Session
#             data = self.angel_client.generateSession(CLIENT_CODE, PASSWORD, otp)
            
#             if data and data.get("status"):
#                 self.auth_details["jwtToken"] = data['data']['jwtToken']
#                 self.auth_details["clientCode"] = CLIENT_CODE
#                 self.auth_details["apiKey"] = API_KEY
                
#                 # 3. Get Feed Token for WebSocket
#                 feed_token = self.angel_client.getFeedToken()
#                 self.auth_details["feedToken"] = feed_token
                
#                 self.strategy = IntradayEqtyStrategy(self.angel_client)
#                 self.auth_label.configure(text="Login Success", text_color="green")
#                 logger.info("Authentication successful.")
#                 return True
#             else:
#                 error_msg = data.get("message", "Unknown login error.")
#                 self.auth_label.configure(text=f"Login Failed: {error_msg}", text_color="red")
#                 logger.error(f"Login failed: {error_msg}")
#                 return False
                
#         except Exception as e:
#             self.auth_label.configure(text="Login Failed: Exception", text_color="red")
#             logger.error(f"Authentication Exception: {e}")
#             return False

#     def build_ui(self):
#         # --- Authentication Status Bar ---
#         self.auth_frame = ctk.CTkFrame(self, fg_color="#333333")
#         self.auth_frame.pack(fill='x', padx=10, pady=(10, 5))
#         self.auth_label = ctk.CTkLabel(self.auth_frame, text="Initializing...", text_color="white", font=ctk.CTkFont(weight="bold"))
#         self.auth_label.pack(padx=10, pady=5)
        
#         # --- Input Frame ---
#         input_frame = ctk.CTkFrame(self)
#         input_frame.pack(fill='x', padx=10, pady=(0, 5))

#         self.input_symbol = ctk.CTkEntry(input_frame, placeholder_text="Enter Symbol (e.g., HDFCBANK)")
#         self.input_symbol.pack(side='left', fill='x', expand=True, padx=(10, 5))

#         add_btn = ctk.CTkButton(input_frame, text="Add Symbol", command=self.resolve_symbol)
#         add_btn.pack(side='left', padx=5)
        
#         remove_btn = ctk.CTkButton(input_frame, text="Remove Selected", command=self.remove_selected, fg_color="red")
#         remove_btn.pack(side='left', padx=5)
        
#         # --- Action Buttons ---
#         action_frame = ctk.CTkFrame(self)
#         action_frame.pack(fill='x', padx=10, pady=5)
        
#         self.start_btn = ctk.CTkButton(action_frame, text="▶️ Start Stream", command=self.start_stream, fg_color="green")
#         self.start_btn.pack(side='left', fill='x', expand=True, padx=(0, 5))
        
#         self.stop_btn = ctk.CTkButton(action_frame, text="⏹️ Stop Stream", command=self.stop_stream, fg_color="darkred", state="disabled")
#         self.stop_btn.pack(side='left', fill='x', expand=True, padx=(5, 0))

#         # --- Watchlist Table (Treeview) ---
#         style = ttk.Style()
#         style.theme_use("default")
#         # Custom styling for dark mode compatibility (adjust colors as needed)
#         style.configure("Treeview", background="#2a2d2e", foreground="white", fieldbackground="#2a2d2e", borderwidth=0)
#         style.map('Treeview', background=[('selected', '#1f538d')])
        
#         columns = ("Symbol", "Token", "LTP", "Open", "High", "Low", "Close", "Signal")
#         self.tree = ttk.Treeview(self, columns=columns, show="headings")
        
#         for col in columns:
#             self.tree.heading(col, text=col, anchor=tk.CENTER)
#             self.tree.column(col, anchor=tk.CENTER, width=100 if col != "Symbol" else 120)

#         self.tree.pack(fill='both', expand=True, padx=10, pady=(0, 10))

#     # ---------------- Watchlist Management ----------------
#     def resolve_symbol(self):
#         """Resolves symbol, adds it to the list, and fetches the initial pivot (REST API)."""
#         if not self.strategy:
#             messagebox.showerror("System Error", "Strategy not initialized. Check login status.")
#             return

#         name_or_symbol = self.input_symbol.get().strip()
#         if not name_or_symbol:
#             messagebox.showwarning("Input Error", "Please enter a symbol or name")
#             return
            
#         try:
#             mapping = self.resolver.resolve_symbol_tradefinder(name_or_symbol)

#             if not mapping:
#                 messagebox.showerror("Resolve Error", f"No token found for {name_or_symbol} in local map.")
#                 return

#             symbol = mapping["trading_symbol"]
#             token = mapping["token"]

#             if not any(x['symbol'] == symbol for x in self.watchlist):
                
#                 # CRITICAL STEP: Fetch historical data and initialize pivot (Synchronous REST API call)
#                 pivot_high, pivot_low = self.strategy.initialize_pivot_for_token(symbol, token)
                
#                 if pivot_high is None or pivot_low is None:
#                     messagebox.showwarning("Pivot Warning", f"Could not calculate initial pivot for {symbol}. Check the log for API errors.")

#                 self.watchlist.append({"symbol": symbol, "token": token})
#                 self.update_watchlist_grid()

#             self.input_symbol.delete(0, tk.END)
#         except Exception as e:
#             messagebox.showerror("Resolve Error", str(e))
#             self.strategy.logger.error(f"Error during symbol resolution: {e}")


#     def update_watchlist_grid(self):
#         """Refreshes the Treeview display."""
#         for row in self.tree.get_children():
#             self.tree.delete(row)
            
#         for item in self.watchlist:
#             # Initial display values
#             initial_values = (
#                 item["symbol"], 
#                 item["token"], 
#                 "0.00", "0.00", "0.00", "0.00", "0.00", "Waiting"
#             )
#             self.tree.insert("", tk.END, values=initial_values)

#     def remove_selected(self):
#         """Removes the selected item."""
#         # ... (implementation as in the previous response) ...
#         selected_items = self.tree.selection()
#         if not selected_items:
#             return

#         for item_id in selected_items:
#             values = self.tree.item(item_id)['values']
#             symbol = values[0]
#             token = values[1]
            
#             self.watchlist = [item for item in self.watchlist if item['token'] != token]
            
#             if symbol in self.strategy.pivot_cache:
#                 del self.strategy.pivot_cache[symbol]
                
#             self.tree.delete(item_id)
        
#         self.strategy.logger.info(f"Removed {len(selected_items)} symbols from watchlist.")

#     # ---------------- Streaming Actions ----------------
#     def start_stream(self):
#         """Starts the real-time WebSocket stream."""
#         if not self.strategy or not self.strategy.angel_client:
#             messagebox.showerror("Error", "Authentication failed or client not ready.")
#             return

#         if not self.watchlist:
#             messagebox.showwarning("Start Stream", "Watchlist is empty. Add symbols first.")
#             return

#         token_list = [str(item["token"]) for item in self.watchlist]
        
#         # Start the WebSocket with tokens
#         self.strategy.start_websocket(token_list, self.on_tick, self.auth_details)
        
#         self.start_btn.configure(state="disabled")
#         self.stop_btn.configure(state="normal")
#         logger.info("Real-time stream initiated.")

#     def stop_stream(self):
#         """Stops the WebSocket stream."""
#         self.strategy.stop_websocket()
#         self.start_btn.configure(state="normal")
#         self.stop_btn.configure(state="disabled")
#         logger.info("Real-time stream stopped.")

#     # ---------------- Tick Processing (Main Engine) ----------------
#     def on_tick(self, tick):
#         """Processes a single real-time tick from the WebSocket (runs on WS thread)."""
#         try:
#             token = str(tick.get("token"))
#             # SmartAPI price is typically in paise, convert to rupees
#             ltp = tick.get("last_traded_price") / 100.0 if tick.get("last_traded_price") else None
            
#             if ltp is None:
#                 return

#             candle = self.strategy.update_candle(token, ltp, interval_min=5)

#             # Map token back to symbol to get cached pivot
#             symbol = next((item['symbol'] for item in self.watchlist if str(item['token']) == token), None)
#             if not symbol:
#                 return

#             # Get Pre-calculated Pivot and Generate Signal
#             signal = "HOLD"
#             pivot_high, pivot_low = self.strategy.get_pivot(symbol) 
            
#             if pivot_high and pivot_low:
#                 # Simple Pivot Breakout Strategy:
#                 if candle['close'] > pivot_high:
#                     signal = "BREAKOUT BUY"
#                 elif candle['close'] < pivot_low:
#                     signal = "BREAKDOWN SELL"
#             else:
#                  signal = "No Pivot"

#             # Update TreeView (safely on the main thread)
#             self.after(0, self.update_treeview_data, token, ltp, candle, signal)
            
#         except Exception as e:
#             self.strategy.logger.error(f"Error processing tick for token {token}: {e}")
            
#     def update_treeview_data(self, token, ltp, candle, signal):
#         """Helper function to safely update the Treeview on the main thread."""
#         for row in self.tree.get_children():
#             values = self.tree.item(row)["values"]
#             if str(values[1]) == token:
#                 self.tree.item(row, values=(
#                     values[0], token,
#                     f"{ltp:.2f}", 
#                     f"{candle['open']:.2f}",
#                     f"{candle['high']:.2f}",
#                     f"{candle['low']:.2f}",
#                     f"{candle['close']:.2f}",
#                     signal
#                 ))
#                 break

# # ----------------------------------------------------------------------
# # 3. Main Application Entry Point
# # ----------------------------------------------------------------------

# if __name__ == "__main__":
#     app = ctk.CTk()
#     app.title("SmartAPI Intraday Algo Dashboard")
#     ctk.set_appearance_mode("Dark")
#     app.geometry("1000x600")

#     tab = IntradayWatchlistTab(app)
#     tab.pack(fill="both", expand=True)

#     def on_closing():
#         """Ensure WebSocket is closed before exit."""
#         if tab.strategy and tab.strategy.is_streaming:
#             tab.strategy.stop_websocket()
#         app.destroy()

#     app.protocol("WM_DELETE_WINDOW", on_closing)
#     app.mainloop()
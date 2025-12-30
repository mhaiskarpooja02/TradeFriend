
import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime, timedelta
import os, json, logging
import threading

from core.trade_manager import TradeManager
from utils.TradeFriendManager import TradeFriendManager

# Placeholder imports (these will be resolved if 'core' and 'utils' are copied from old project)
try:
    from core.trade_plan_service import TradePlanService
    from utils.symbol_resolver import SymbolResolver
except Exception:
    TradePlanService = object
    SymbolResolver = object

logger = logging.getLogger(__name__)
CONTROL_FILE = "control/control.json"

class DashboardTab(ctk.CTkFrame):
    def __init__(self, parent, trader=None):
        super().__init__(parent)
       
        self.trader = TradeManager()   # ✅ store trader reference
        self.daily_refresh_done = False
        self.monitoring_active = False
        self.auto_refresh_active = True   # enabled by default

        self.tradefriendtrader = TradeFriendManager()

        # ----------------- Layout -----------------
        self.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Monitoring Box ---
        monitor_box = ctk.CTkFrame(self)
        monitor_box.pack(fill="x", pady=8)

        self.status_label = ctk.CTkLabel(monitor_box, text="Status: Idle")
        self.status_label.pack(pady=(5, 10))

        self.start_monitor_btn = ctk.CTkButton(
            monitor_box, text="Start Monitoring", command=self.start_monitoring
        )
        self.start_monitor_btn.pack(side="left", padx=10, pady=5)

        self.stop_monitor_btn = ctk.CTkButton(
            monitor_box, text="Stop Monitoring",
            command=self.stop_monitoring, state="disabled"
        )
        self.stop_monitor_btn.pack(side="left", padx=10, pady=5)

        # --- Data Box ---
        data_box = ctk.CTkFrame(self)
        data_box.pack(fill="x", pady=8)

        self.refresh_btn = ctk.CTkButton(
            data_box, text="Refresh Data", command=self.manual_refresh
        )
        self.refresh_btn.pack(side="left", padx=10, pady=5)

        self.delete_btn = ctk.CTkButton(
            data_box, text="Delete Old Files", command=self.delete_old_files
        )
        self.delete_btn.pack(side="left", padx=10, pady=5)

        # --- Auto Refresh Toggle ---
        toggle_box = ctk.CTkFrame(self)
        toggle_box.pack(fill="x", pady=8)

        self.start_auto_btn = ctk.CTkButton(
            toggle_box, text="Enable Auto Refresh", command=self.start_auto_refresh,
            state="disabled"  # already enabled at start
        )
        self.start_auto_btn.pack(side="left", padx=10, pady=5)

        self.stop_auto_btn = ctk.CTkButton(
            toggle_box, text="Disable Auto Refresh", command=self.stop_auto_refresh
        )
        self.stop_auto_btn.pack(side="left", padx=10, pady=5)

        # Start auto-check loop
        self.after(1000, self.auto_daily_refresh_check)

        # --- TradeFriend Controls ---
        tf_box = ctk.CTkFrame(self)
        tf_box.pack(fill="x", pady=8)

        self.tf_scan_btn = ctk.CTkButton(
            tf_box, text="Run TradeFriend Daily Scan",
           command=self.tf_run_daily_scan
        )
        self.tf_scan_btn.pack(side="left", padx=10, pady=5)

        self.tf_confirm_btn = ctk.CTkButton(
            tf_box, text="Run Morning Confirmation",
            command=self.tf_run_morning_confirm
        )
        self.tf_confirm_btn.pack(side="left", padx=10, pady=5)

        self.tf_monitor_btn = ctk.CTkButton(
            tf_box, text="Run Trade Monitor",
            command=self.tf_run_monitor
        )
        self.tf_monitor_btn.pack(side="left", padx=10, pady=5)

    # ----------------- Control File Helpers -----------------
    def load_control(self):
        if os.path.exists(CONTROL_FILE):
            try:
                with open(CONTROL_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_control(self, control_dict):
        os.makedirs(os.path.dirname(CONTROL_FILE) or ".", exist_ok=True)
        tmp = CONTROL_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(control_dict, f)
        os.replace(tmp, CONTROL_FILE)

    # ----------------- Manual Refresh -----------------
    def manual_refresh(self):
        self.status_label.configure(text="Status: Running manual refresh...")
        try:
            if self.trader and hasattr(self.trader, 'daily_refresh'):
                self.trader.daily_refresh(force=True)
            self.daily_refresh_done = True
            self.status_label.configure(text="Status: Manual refresh complete")
        except Exception as e:
            messagebox.showerror("Error", f"Manual refresh failed: {e}")
            self.status_label.configure(text="Status: Error during refresh")

    # ----------------- Delete Old Files -----------------
    def delete_old_files(self):
        try:
            folders = ["input", "output", "logs"]
            cutoff = datetime.now() - timedelta(days=7)
            deleted_items = []

            for folder in folders:
                if not os.path.exists(folder):
                    continue

                for item in os.listdir(folder):
                    full_path = os.path.join(folder, item)

                    try:
                        # Handle dated subfolders (e.g., 2025-10-01)
                        if os.path.isdir(full_path):
                            try:
                                folder_date = datetime.strptime(item, "%Y-%m-%d")
                                if folder_date < cutoff:
                                    import shutil
                                    shutil.rmtree(full_path)
                                    deleted_items.append(full_path)
                                    continue
                            except ValueError:
                                pass  # Not a dated folder — fall through to timestamp check

                        # Handle files
                        mtime = datetime.fromtimestamp(os.path.getmtime(full_path))
                        if mtime < cutoff:
                            if os.path.isdir(full_path):
                                import shutil
                                shutil.rmtree(full_path)
                            else:
                                os.remove(full_path)
                            deleted_items.append(full_path)

                    except Exception as inner_e:
                        logger.warning(f"Skip deletion for {full_path}: {inner_e}")

            msg = (
                f"Deleted items:\n" + "\n".join(deleted_items)
                if deleted_items
                else "No old files found in input, output, or logs folders."
            )
            messagebox.showinfo("Cleanup", msg)

        except Exception as e:
            logger.error(f"Cleanup failed: {e}", exc_info=True)
            messagebox.showerror("Error", f"Cleanup failed: {e}")

    # ----------------- Auto Refresh -----------------
    def auto_daily_refresh_check(self):
        if not self.auto_refresh_active:
            return  # Skip loop if disabled

        now = datetime.today()
        today_str = now.strftime("%Y-%m-%d")

        control = self.load_control()
        last_run_date = control.get("last_daily_refresh_date", "")

        if last_run_date != today_str:  # not run today
            if now.hour > 15 or (now.hour == 15 and now.minute >= 30):
                self.status_label.configure(text="Status: Auto refresh running...")
                try:
                    if self.trader and hasattr(self.trader, 'daily_refresh'):
                        self.trader.daily_refresh()
                    control["last_daily_refresh_date"] = today_str
                    self.save_control(control)
                    self.status_label.configure(text="Status: Auto refresh complete")
                except Exception as e:
                    messagebox.showerror("Error", f"Auto refresh failed: {e}")
                    self.status_label.configure(text="Status: Auto refresh error")

        # Schedule next check in 15 min
        self.after(15 * 60 * 1000, self.auto_daily_refresh_check)

    def start_auto_refresh(self):
        if not self.auto_refresh_active:
            self.auto_refresh_active = True
            self.start_auto_btn.configure(state="disabled")
            self.stop_auto_btn.configure(state="normal")
            self.status_label.configure(text="Status: Auto refresh enabled")
            self.after(1000, self.auto_daily_refresh_check)

    def stop_auto_refresh(self):
        self.auto_refresh_active = False
        self.start_auto_btn.configure(state="normal")
        self.stop_auto_btn.configure(state="disabled")
        self.status_label.configure(text="Status: Auto refresh disabled")

    # ----------------- Monitoring -----------------
    def start_monitoring(self):
        if not self.monitoring_active:
            self.monitoring_active = True
            self.start_monitor_btn.configure(state="disabled")
            self.stop_monitor_btn.configure(state="normal")
            self.status_label.configure(text="Status: Monitoring started")
            self.monitor_loop()

    def stop_monitoring(self):
        self.monitoring_active = False
        self.start_monitor_btn.configure(state="normal")
        self.stop_monitor_btn.configure(state="disabled")
        self.status_label.configure(text="Status: Monitoring stopped")

    def monitor_loop(self):
        if self.monitoring_active:
            try:
                if self.trader and hasattr(self.trader, 'monitor_targets'):
                    self.trader.monitor_targets()
                self.status_label.configure(
                    text=f"Status: Last monitor run: {datetime.now().strftime('%H:%M:%S')}"
                )
            except Exception as e:
                messagebox.showerror("Error", f"Monitoring failed: {e}")
                self.status_label.configure(text="Status: Monitoring error")
            # Repeat every 5 minutes
            self.after(5 * 60 * 1000, self.monitor_loop)
    
    def tf_run_daily_scan(self):
        def worker():   
            try:
                self.status_label.configure(
                    text="Status: TradeFriend daily scan running..."
                )
                #self.update_idletasks()
                logger.info(" TradeFriend daily scan started")
                self.tradefriendtrader.tf_daily_scan()
                logger.info(" TradeFriend daily scan completed")
                self.status_label.configure(
                    text="Status: TradeFriend daily scan complete"
                )
            except Exception as e:
                messagebox.showerror("Error", f"Daily scan failed: {e}")
                self.status_label.configure(text="Status: Daily scan error")
        threading.Thread(target=worker, daemon=True).start()        


    def tf_run_morning_confirm(self):
            try:
                self.status_label.configure(
                    text="Status: TradeFriend morning confirmation running..."
                )
                self.update_idletasks()

                CAPITAL = 100000
                self.tradefriendtrader.tf_morning_confirm(capital=CAPITAL)

                self.status_label.configure(
                    text="Status: TradeFriend morning confirmation complete"
                )
            except Exception as e:
                messagebox.showerror("Error", f"Morning confirmation failed: {e}")
                self.status_label.configure(text="Status: Morning confirmation error")


    def tf_run_monitor(self):
            try:
                self.status_label.configure(
                    text="Status: TradeFriend monitoring running..."
                )
                self.update_idletasks()

                self.tradefriendtrader.tf_monitor()

                self.status_label.configure(
                    text="Status: TradeFriend monitoring complete"
                )
            except Exception as e:
                messagebox.showerror("Error", f"Monitoring failed: {e}")
                self.status_label.configure(text="Status: Monitoring error")


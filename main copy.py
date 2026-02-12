import os
import socket
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from datetime import datetime

from app.config_popups.LicenseKeyPopup import LicenseKeyPopup
from app.config_popups.EmailPopup import EmailPopup
from app.config_popups.BrokerConfigPopup import BrokerConfigPopup
from app.pages.TradeFriendDashboard import TradeFriendDashboard
from app.pages.RangeboundTab import RangeboundTab
from app.pages.TradeSetupTab import TradeSetupTab
from app.pages.HoldingsTab import HoldingsTab
from app.pages.TokenManagerPage import TokenManagerPage
from app.pages.DashboardTab import DashboardTab
from app.pages.TradeAnalysisTab import TradeAnalysisTab
from app.pages.TradeFriendSettingsPopup import TradeFriendSettingsPopup

from db.LicenseDB import LicenseDB

# -----------------------------
# Page Imports (your classes)
# -----------------------------
# from pages.dashboardtab import DashboardPage
# from pages.trade_setup import TradeSetupTab
# from pages.holdings import HoldingsTab
# from pages.token_manager import TokenManagerPage
# from pages.trade_analysis import TradeAnalysisPage

# -----------------------------
# MAIN APPLICATION
# -----------------------------
class TradeMadeEasyApp(tb.Window):
    def __init__(self):
        super().__init__(title="TradeMadeEasy", themename="vapor")
        self.geometry("1200x700")

        # Header
        self.header_frame = tb.Frame(self)
        self.header_frame.pack(fill=X)

        self.app_name_label = tb.Label(
            self.header_frame, text="TradeMadeEasy", font=("Arial", 18, "bold")
        )
        self.app_name_label.pack(side=LEFT, padx=10, pady=5)

        # Theme dropdown
        self.style.theme_use("vapor")     # ensure theme is applied
        self.theme_var = tk.StringVar(value="vapor")  # dropdown shows same
        self.theme_menu = tb.Combobox(
            self.header_frame,
            textvariable=self.theme_var,
            values=self.style.theme_names(),
            width=15
        )
        self.theme_menu.pack(side=RIGHT, padx=10)
        self.theme_menu.bind("<<ComboboxSelected>>", self.change_theme)

        # Trade settings button
        self.trade_settings_button = tb.Button(
            self.header_frame,
            text="💼 Trade Settings",
            bootstyle=INFO,
            command=self.open_trade_settings
        )
        self.trade_settings_button.pack(side=RIGHT, padx=5)


        # Config button
        self.config_button = tb.Button(
            self.header_frame, text="⚙️ Config", bootstyle=INFO, command=self.open_config
        )
        self.config_button.pack(side=RIGHT, padx=5)

        # Body frame
        self.body_frame = tb.Frame(self)
        self.body_frame.pack(fill=BOTH, expand=YES)

        # Left navigation
        self.nav_frame = tb.Frame(self.body_frame, width=180)
        self.nav_frame.pack(side=LEFT, fill=Y, padx=(0,5), pady=5)

        self.pages_frame = tb.Frame(self.body_frame)
        self.pages_frame.pack(side=LEFT, fill=BOTH, expand=YES, padx=5, pady=5)

        self.pages = {}
        self.after(100, self.run_startup_checks)

    # -----------------------------
    # Navigation buttons
    # -----------------------------
    def create_nav_buttons(self):
        nav_buttons = [
            ("Dashboard", DashboardTab),
            ("Trade Setup", TradeSetupTab),
            ("Holdings", HoldingsTab),
            ("Token Manager", TokenManagerPage),
            ("Rangebound", RangeboundTab),
            ("Trade Analysis", TradeAnalysisTab),
            ("Watchlist Dashboard", TradeFriendDashboard)
              
        ]

        for name, page_class in nav_buttons:
            btn = tb.Button(
                self.nav_frame, text=name, bootstyle=SECONDARY, width=20,
                command=lambda n=name, cls=page_class: self.show_page(n, cls)
            )
            btn.pack(pady=5)

    # -----------------------------
    # Show selected page
    # -----------------------------
    def show_page(self, name, page_class=None):
       # Hide all pages (if they exist)
       for page in self.pages.values():
           if page.winfo_exists():
               page.pack_forget()

       # Create page if not already created
       if name not in self.pages and page_class:
           page = page_class(self.pages_frame)
           self.pages[name] = page

       page = self.pages.get(name)

       # Safely show the selected page
       if page and page.winfo_exists():
           page.pack(fill=BOTH, expand=YES)


    # -----------------------------
    # Theme change
    # -----------------------------
    def change_theme(self, event=None):
        selected = self.theme_var.get()
        try:
            self.style.theme_use(selected)
        except Exception as e:
            messagebox.showerror("Theme Error", f"Failed to apply theme: {e}")

    # -----------------------------
    # Trade settings page
    # -----------------------------
    def open_trade_settings(self):
        """Open the TradeFriend settings popup"""
        try:
            TradeFriendSettingsPopup(self)
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Failed to open trade settings window:\n{e}"
            )


    # -----------------------------
    # Config page placeholder
    # -----------------------------
    def open_config(self):
        """Open the CustomTkinter broker configuration popup"""
        try:
            BrokerConfigPopup(self)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open config window:\n{e}")

    def run_startup_checks(self):
        # -----------------------------
        # Internet check
        # -----------------------------
        try:
            self.validate_internet()
        except RuntimeError:
            messagebox.showerror(
                "No Internet Connection",
                "Internet connection is required to start TradeMadeEasy."
            )
            self.destroy()
            return

        # -----------------------------
        # License checks
        # -----------------------------
        repo = LicenseDB()

        # 1️⃣ Fresh install → ask email
        if not repo.has_any_record():
            EmailPopup(self)
            return

        # 2️⃣ Email stored but no license key yet
        if repo.has_email() and not repo.has_license_key():
            LicenseKeyPopup(self)
            return

        # 3️⃣ License key entered but not verified
        if repo.has_license_key() and not repo.is_verified():
            LicenseKeyPopup(self)
            return

        # -----------------------------
        # ✅ ALL GOOD → Load app
        # -----------------------------
        self.create_nav_buttons()
        self.show_page("Dashboard")

    @staticmethod
    def validate_internet(timeout: int = 3) -> None:
        """
        Raises RuntimeError if internet is not available.
        Keeps logic strict for app startup.
        """
        try:
            socket.setdefaulttimeout(timeout)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("8.8.8.8", 53))
            sock.close()
        except Exception:
            raise RuntimeError("Internet connection is required.")

# -----------------------------
# Run Application
# -----------------------------
if __name__ == "__main__":
    app = TradeMadeEasyApp()
    app.mainloop()

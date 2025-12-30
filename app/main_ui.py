
# app/main_ui.py - launcher for TradeMadeEasy (left navigation + header)
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
import os

# Import the pages (these files are created by setup script)
from app.pages import TradeFriendDashboard
from app.pages.DashboardTab import DashboardTab
from app.pages.TradeAnalysisTab import TradeAnalysisTab
from app.pages.TradeSetupTab import TradeSetupTab
from app.pages.HoldingsTab import HoldingsTab
from app.pages.TokenManagerPage import TokenManagerPage
from app.config_popups.BrokerConfigPopup import BrokerConfigPopup

def run_app():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("TradeMadeEasy")
    root.geometry("1200x750")

    # Top header
    header = ctk.CTkFrame(root, height=52)
    header.pack(fill="x", side="top")

    title_lbl = ctk.CTkLabel(header, text="TradeMadeEasy", font=("Arial", 18, "bold"))
    title_lbl.pack(side="left", padx=12)

    # Right side of header - theme selector + config icon
    header_right = ctk.CTkFrame(header, fg_color="transparent")
    header_right.pack(side="right", padx=12)

    def on_theme_change(value):
        # value expected 'Dark' or 'Light'
        if value.lower().startswith("dark"):
            ctk.set_appearance_mode("dark")
        else:
            ctk.set_appearance_mode("light")

    theme_combo = ctk.CTkComboBox(header_right, values=["Dark", "Light"], width=120, command=on_theme_change)
    theme_combo.set("Dark")
    theme_combo.pack(side="left", padx=(0,8))

    def open_config():
        # open broker config popup
        BrokerConfigPopup(root)

    cfg_btn = ctk.CTkButton(header_right, text="⚙️", width=36, height=36, command=open_config)
    cfg_btn.pack(side="left", padx=(4,0))

    # Main layout frames
    content = ctk.CTkFrame(root)
    content.pack(fill="both", expand=True, padx=8, pady=8)

    nav_frame = ctk.CTkFrame(content, width=200)
    nav_frame.pack(side="left", fill="y", padx=(0,8), pady=4)

    main_frame = ctk.CTkFrame(content)
    main_frame.pack(side="left", fill="both", expand=True, pady=4)

    # Create page instances but don't pack them yet
    pages = {}
    pages["Dashboard"] = DashboardTab(main_frame)
    pages["TradeAnalysis"] = TradeAnalysisTab(main_frame)
    pages["TradeSetup"] = TradeSetupTab(main_frame)
    pages["Holdings"] = HoldingsTab(main_frame)
    pages["TokenManager"] = TokenManagerPage(main_frame)
    pages["TradeFriendDashboard"] = TradeFriendDashboard(main_frame)

    # Navigation buttons
    def show_page(key):
        # hide all pages
        for p in pages.values():
            p.pack_forget()
        pages[key].pack(fill="both", expand=True)

    btn_specs = [
        ("Dashboard", "Dashboard"),
        ("TradeFriendDashboard", "TradeFriendDashboard"),
        ("Trade Finder", "TradeSetup"),
        ("Holdings", "Holdings"),
        ("Trade Analysis", "TradeAnalysis"),
        ("Token Manager", "TokenManager"),
    ]

    for text, key in btn_specs:
        btn = ctk.CTkButton(nav_frame, text=text, width=180, command=lambda k=key: show_page(k))
        btn.pack(pady=8, padx=8)

    # Show default page
    show_page("Dashboard")

    root.mainloop()

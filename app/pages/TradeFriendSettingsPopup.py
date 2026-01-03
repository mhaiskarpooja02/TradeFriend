import tkinter as tk
from tkinter import ttk, messagebox

from db.TradeFriendSettingsRepo import TradeFriendSettingsRepo


class TradeFriendSettingsPopup(tk.Toplevel):
    """
    Popup UI for managing TradeFriend capital & risk settings
    (Amount-based, trader friendly)
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("TradeFriend Settings")
        self.geometry("520x420")
        self.resizable(False, False)

        self.settings = TradeFriendSettingsRepo()
        self.inputs = {}

        self._build_ui()
        self._load_values()

    # -------------------------------------------------
    # UI
    # -------------------------------------------------
    def _build_ui(self):
        container = ttk.Frame(self, padding=14)
        container.pack(fill="both", expand=True)

        # ===== Capital =====
        ttk.Label(
            container,
            text="Capital Configuration",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 8))

        self._add_field(container, "Total Capital (₹)", "total_capital")
        self._add_field(container, "Swing Trading Capital (₹)", "swing_capital")
        self._add_field(container, "Max Active Capital (₹)", "max_active_capital")
        self._add_field(container, "Per Trade Capital Cap (₹)", "per_trade_cap")

        ttk.Separator(container).pack(fill="x", pady=12)

        # ===== Risk =====
        ttk.Label(
            container,
            text="Risk Management",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 8))

        self._add_field(container, "Risk % per Trade", "risk_percent")
        self._add_field(container, "Max Open Trades", "max_open_trades")

        ttk.Separator(container).pack(fill="x", pady=14)

        # ===== Buttons =====
        btns = ttk.Frame(container)
        btns.pack(fill="x")

        ttk.Button(btns, text="Save Settings", command=self._save)\
            .pack(side="right", padx=6)

        ttk.Button(btns, text="Close", command=self.destroy)\
            .pack(side="right")

    def _add_field(self, parent, label, key):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)

        ttk.Label(row, text=label, width=32).pack(side="left")

        entry = ttk.Entry(row, width=20)
        entry.pack(side="right")

        self.inputs[key] = entry

    # -------------------------------------------------
    # LOAD / SAVE
    # -------------------------------------------------
    def _load_values(self):
        for key, entry in self.inputs.items():
            val = self.settings.get(key)
            if val is not None:
                entry.delete(0, tk.END)
                entry.insert(0, str(val))

    def _save(self):
        try:
            for key, entry in self.inputs.items():
                value = entry.get().strip()
                if value == "":
                    continue

                if key in ("risk_percent",):
                    value = float(value)
                else:
                    value = int(value)

                self.settings.set(key, value)

            messagebox.showinfo("Saved", "Settings updated successfully")
            self.destroy()

        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numeric values")
        except Exception as e:
            messagebox.showerror("Error", str(e))

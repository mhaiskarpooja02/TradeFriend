import os
import zipfile
import logging
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import ttkbootstrap as tb

# -------------------------------------------------------------------------
# ✅ Safe imports with fallback (so UI doesn't crash if module not ready)
# -------------------------------------------------------------------------
logger = logging.getLogger(__name__)

try:
    from config.settings import NSE_EQTY_FILE, INPUT_BASE, OUTPUT_FOLDER
    from core.trade_finder_runner import run_trade_finder
    logger.info("✅ Trade Finder imports loaded successfully.")
except Exception as e:
    logger.warning(f" Trade Finder imports failed — using fallback: {e}")
    NSE_EQTY_FILE = "data/nse_eqty.json"
    INPUT_BASE = "input"
    OUTPUT_FOLDER = "output"

    def run_trade_finder(input_dir: str, output_dir: str):
        """Fallback dummy function if core runner not loaded."""
        logger.info(f"⚙️ Mock Trade Finder called → input: {input_dir}, output: {output_dir}")
        return True, []


# -------------------------------------------------------------------------
# ✅ Trade Finder UI Class
# -------------------------------------------------------------------------
class TradeSetupTab(tb.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent

          # ✅ Reuse parent's style if it exists, otherwise create one
       
        # === Header ===
        tb.Label(self, text="🔍 Trade Finder", font=("Arial", 16, "bold")).pack(
            anchor="w", pady=(8, 6), padx=8
        )

        # === Controls Row ===
        control_frame = tb.Frame(self)
        control_frame.pack(fill="x", padx=8, pady=6)

        tb.Label(control_frame, text="Naming Prefix:").pack(side="left", padx=(4, 6))

        self.naming_var = tk.StringVar(value="ChartInk_")
        self.naming_menu = tb.Combobox(
            control_frame,
            values=["ChartInk_", "MyScreen_"],
            textvariable=self.naming_var,
            width=20,
        )
        self.naming_menu.pack(side="left", padx=(0, 8))

        # ✅ NEW — Folder Selector
        tb.Label(control_frame, text="📁 Select Date Folder:").pack(side="left", padx=(6, 6))
        self.folder_var = tk.StringVar()
        self.folder_menu = tb.Combobox(control_frame, textvariable=self.folder_var, width=15)
        self.folder_menu.pack(side="left", padx=(0, 8))
        self.folder_menu.bind("<<ComboboxSelected>>", lambda e: self.load_today_files())

        tb.Button(control_frame, text="Upload File", bootstyle="info", command=self.upload_file).pack(side="left", padx=8)
        tb.Button(control_frame, text="Refresh List", bootstyle="secondary", command=self.load_today_files).pack(side="left", padx=8)
        tb.Button(control_frame, text="🚀 Trade Finder", bootstyle="success", command=self.run_trade_search).pack(side="left", padx=8)

        # === Progress Label ===
        self.progress_label = tb.Label(self, text="", font=("Arial", 12, "italic"))
        self.progress_label.pack(pady=(2, 4))

        # === Table Section ===
        table_frame = tb.Frame(self)
        table_frame.pack(fill="both", expand=True, padx=8, pady=8)

        columns = ("filename", "size_kb", "uploaded_at", "delete")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)

        for c in columns:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=200 if c != "delete" else 100, anchor="center")

        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = tb.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<Button-1>", self.handle_delete_click)

        # === Treeview Style ===
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#2A2A2A",
            foreground="white",
            fieldbackground="#2A2A2A",
            rowheight=24,
            font=("Arial", 11),
        )
        style.map(
            "Treeview",
            background=[("selected", "#1f538d")],
            foreground=[("selected", "white")],
        )

        # Initial load
        self.refresh_folder_list()
        self.load_today_files()

    # -------------------------------------------------------------------------
    # 📁 File Upload
    # -------------------------------------------------------------------------
    def upload_file(self):
        file_path = filedialog.askopenfilename(title="Select CSV file", filetypes=[("CSV Files", "*.csv")])
        if not file_path:
            return

        prefix = self.naming_var.get()
        today = datetime.today().strftime("%Y%m%d")
        ext = os.path.splitext(file_path)[1] or ".csv"

        dest_dir = os.path.join(INPUT_BASE, today)
        os.makedirs(dest_dir, exist_ok=True)

        # Determine next counter file
        existing = [f for f in os.listdir(dest_dir) if f.startswith(prefix + today)]
        next_num = len(existing) + 1
        dest_name = f"{prefix}{today}{next_num:02d}{ext}"
        dest_path = os.path.join(dest_dir, dest_name)

        try:
            with open(file_path, "rb") as src, open(dest_path, "wb") as dst:
                dst.write(src.read())

            logger.info(f"📂 Uploaded file saved as {dest_name}")
            messagebox.showinfo("Upload Successful", f"File saved as: {dest_name}")
            self.load_today_files()
        except Exception as e:
            logger.exception(" Upload failed")
            messagebox.showerror("Error", f"File upload failed:\n{e}")
    # -------------------------------------------------------------------------
    # 📋 refresh folder list
    # -------------------------------------------------------------------------
    def refresh_folder_list(self):
        """Reload list of folders (dates) inside INPUT_BASE, always include today's."""
        os.makedirs(INPUT_BASE, exist_ok=True)
    
        # Collect all existing folders
        folders = sorted(
            [f for f in os.listdir(INPUT_BASE) if os.path.isdir(os.path.join(INPUT_BASE, f))],
            reverse=True,
        )
    
        # Ensure today's folder exists
        today = datetime.today().strftime("%Y%m%d")
        today_path = os.path.join(INPUT_BASE, today)
        if today not in folders:
            os.makedirs(today_path, exist_ok=True)
            folders.insert(0, today)  # put it at the top
    
        # Update combobox values
        self.folder_menu["values"] = folders
    
        # Auto-select today's folder if not set or invalid
        current = self.folder_var.get().strip()
        if not current or current not in folders:
            self.folder_var.set(today)


    # -------------------------------------------------------------------------
    # 📋 Load Today’s Files
    # -------------------------------------------------------------------------
    def load_today_files(self):
       self.tree.delete(*self.tree.get_children())
       selected_folder = self.folder_var.get() or datetime.today().strftime("%Y%m%d")
       dir_path = os.path.join(INPUT_BASE, selected_folder)

       if not os.path.exists(dir_path):
           return

       files = sorted(os.listdir(dir_path))
       for i, fname in enumerate(files):
           fpath = os.path.join(dir_path, fname)
           if not os.path.isfile(fpath):
               continue

           size_kb = os.path.getsize(fpath) // 1024
           uploaded_at = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%H:%M:%S")

           bg_color = "#2A2A2A" if i % 2 == 0 else "#333333"
           self.tree.insert(
               "",
               "end",
               values=(fname, f"{size_kb} KB", uploaded_at, "🗑 Delete"),
               tags=(f"row{i}",),
           )
           self.tree.tag_configure(f"row{i}", background=bg_color, foreground="white")

    # -------------------------------------------------------------------------
    # 🗑 Delete File
    # -------------------------------------------------------------------------
    def handle_delete_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        column = self.tree.identify_column(event.x)
        if column != "#4":
            return

        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return

        fname = self.tree.item(row_id, "values")[0]
        today = datetime.today().strftime("%Y%m%d")
        fpath = os.path.join(INPUT_BASE, today, fname)

        if not os.path.exists(fpath):
            return

        try:
            os.remove(fpath)
            logger.info(f"🗑 Deleted file {fname}")
            messagebox.showinfo("Deleted", f"{fname} removed successfully.")
            self.load_today_files()
        except Exception as e:
            logger.exception(" Failed to delete file")
            messagebox.showerror("Error", f"Could not delete {fname}:\n{e}")

    # -------------------------------------------------------------------------
    # 🚀 Run Trade Finder
    # -------------------------------------------------------------------------
    def run_trade_search(self):
        selected_folder = self.folder_var.get().strip()
        if not selected_folder:
            messagebox.showwarning("No Folder Selected", "Please select a date folder first.")
            return

        dir_path = os.path.join(INPUT_BASE, selected_folder)
        if not os.path.exists(dir_path) or not os.listdir(dir_path):
            messagebox.showwarning("No Files", f"No files found in folder: {selected_folder}")
            return

        self.progress_label.configure(text=f"⏳ Running Trade Finder for {selected_folder}...")
        self.update_idletasks()

        output_dir = os.path.join(OUTPUT_FOLDER, selected_folder)
        os.makedirs(output_dir, exist_ok=True)

        try:
            logger.info(f"🚀 Starting Trade Finder → input: {dir_path}, output: {output_dir}")
            success, output_files = run_trade_finder(dir_path, output_dir)

            if not success or not output_files:
                messagebox.showinfo("Trade Finder", "No signals found or no output generated.")
                logger.warning("⚠️ Trade Finder returned no data.")
                return

            # Zip all output files
            zip_path = os.path.join(OUTPUT_FOLDER, f"TradeFinder_{selected_folder}.zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for f in output_files:
                    if os.path.exists(f):
                        zipf.write(f, os.path.basename(f))

            save_path = filedialog.asksaveasfilename(
                title="Save TradeFinder ZIP",
                defaultextension=".zip",
                initialfile=os.path.basename(zip_path),
                filetypes=[("ZIP Files", "*.zip")],
            )

            if save_path:
                os.replace(zip_path, save_path)
                messagebox.showinfo("Trade Finder", f"ZIP file saved successfully:\n{save_path}")
                logger.info(f"✅ Trade Finder ZIP saved → {save_path}")

            # Cleanup intermediate files
            for f in output_files:
                if os.path.exists(f):
                    os.remove(f)

        except Exception as e:
            logger.exception("💥 Trade Finder execution failed")
            messagebox.showerror("Trade Finder Error", f"Error occurred:\n{e}")
        finally:
            self.progress_label.configure(text="")
            self.update_idletasks()


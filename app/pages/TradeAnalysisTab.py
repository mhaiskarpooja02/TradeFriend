import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox
import logging

from core.trade_plan_service import TradePlanService
from utils.symbol_resolver import SymbolResolver
from strategy.market_structure_analyzer import MarketStructureAnalyzer

logger = logging.getLogger(__name__)


class TradeAnalysisTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.service = TradePlanService()
        self.resolver = SymbolResolver()
        self.selected_symbol = None

        # ============ SYMBOL SELECTION SECTION ============
        top_frame = ttk.Labelframe(self, text="Symbol Selection", bootstyle="info")
        top_frame.pack(fill=X, padx=10, pady=10)

        self.mode_var = ttk.StringVar(value="name")
        ttk.Label(top_frame, text="Mode:", bootstyle="secondary").grid(row=0, column=0, padx=5, pady=5, sticky=W)
        ttk.Radiobutton(top_frame, text="By Name", variable=self.mode_var, value="name", bootstyle="primary").grid(row=0, column=1, padx=5, pady=5)
        ttk.Radiobutton(top_frame, text="By Symbol", variable=self.mode_var, value="symbol", bootstyle="primary").grid(row=0, column=2, padx=5, pady=5)

        self.input_symbol = ttk.Entry(top_frame)
        self.input_symbol.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky=EW)

        self.btn_resolve = ttk.Button(top_frame, text="Resolve Symbol", bootstyle="success", command=self.resolve_symbol)
        self.btn_resolve.grid(row=1, column=2, padx=5, pady=5, sticky=EW)

        self.selected_label = ttk.Label(top_frame, text="Selected: None", bootstyle="secondary")
        self.selected_label.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky=W)

        for i in range(3):
            top_frame.grid_columnconfigure(i, weight=1)

        # ============ TRADE PARAMETERS SECTION ============
        params_frame = ttk.Labelframe(self, text="Trade Parameters", bootstyle="info")
        params_frame.pack(fill=X, padx=10, pady=10)

        ttk.Label(params_frame, text="Quantity:", bootstyle="secondary").grid(row=0, column=0, padx=5, pady=5, sticky=W)
        self.qty_input = ttk.Entry(params_frame)
        self.qty_input.grid(row=0, column=1, padx=5, pady=5, sticky=EW)

        ttk.Label(params_frame, text="Entry / Avg Price:", bootstyle="secondary").grid(row=0, column=2, padx=5, pady=5, sticky=W)
        self.price_input = ttk.Entry(params_frame)
        self.price_input.grid(row=0, column=3, padx=5, pady=5, sticky=EW)

        for i in range(4):
            params_frame.grid_columnconfigure(i, weight=1)

        # ============ STRATEGY SELECTION ============
        strat_frame = ttk.Labelframe(self, text="Strategy Selection", bootstyle="info")
        strat_frame.pack(fill=X, padx=10, pady=10, ipady=0, ipadx=0)

        self.strategy_var = ttk.StringVar(value="long")

        # Use grid instead of pack for tighter control and no vertical padding
        options = [("Long-Term", "long"), ("Swing", "swing"), ("Intraday", "intraday")]
        for i, (label, value) in enumerate(options):
            ttk.Radiobutton(
                strat_frame,
                text=label,
                variable=self.strategy_var,
                value=value,
                bootstyle="info"
            ).grid(row=0, column=i, padx=(10 if i == 0 else 5), pady=2, sticky=W)

        # Remove any default expansion
        for i in range(len(options)):
            strat_frame.grid_columnconfigure(i, weight=0)


        # ============ BUTTON + OUTPUT ============
        action_frame = ttk.Frame(self)
        action_frame.pack(fill=X, padx=10, pady=10)

        ttk.Button(action_frame, text="Get Trade Plan", bootstyle="primary", command=self.get_trade_plan).pack(fill=X, padx=5, pady=5)

        self.output_area = ttk.Text(self, height=15, wrap="word")
        self.output_area.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def resolve_symbol(self):
        value = self.input_symbol.get().strip()
        if not value:
            messagebox.showwarning("Input Error", "Please enter a symbol or name")
            return
        try:
            mode = self.mode_var.get()
            if mode == "name":
                logger.info(f"TradeAnalysis Search by name: {value}")
                resolved = self.resolver.get_symbol_tradefinder(value)
                self.selected_symbol = f'{resolved["trading_symbol"]}-EQ'
            else:
                logger.info(f"TradeAnalysis Search by symbol: {value}")
                resolved = self.resolver.resolve_symbol(value)
                self.selected_symbol = f'{resolved["trading_symbol"]}'

            if resolved:
                logger.info(f"resolved vvalue name: {resolved}")
                
                self.selected_label.configure(text=f"Selected: {value} → {self.selected_symbol}")
        except Exception as e:
            messagebox.showerror("Resolve Error", str(e))

    def get_trade_plan(self):
        if not self.selected_symbol:
            messagebox.showwarning("No Symbol", "Please resolve a symbol first")
            return
        try:
            qty = int(self.qty_input.get())
            price = float(self.price_input.get())
            strategy_cls = self.strategy_var.get()
            logger.info(f"Preparing trade plan for {self.selected_symbol}")

            if strategy_cls == "smc":
               
               analyzer = MarketStructureAnalyzer(self.selected_symbol)
               result = analyzer.run_analysis()
               messagebox.showinfo(
                   "Market Structure Report",
                   f"✅ Report Generated!\n\nPDF: {result['pdf']}\nChart: {result['chart']}"
               )
               self.output_area.delete("1.0", "end")
               self.output_area.insert(
                   "end",
                   f"Market Structure analysis completed for {self.selected_symbol}\n"
                   f"PDF: {result['pdf']}\nChart: {result['chart']}\n"
               )
               return  # stop here, no need to run trade plan service


            report_text = self.service.prepare_trade_plan_text(
                self.selected_symbol,
                self.mode_var.get(),
                entry_price=price,
                qty=qty,
                strategy_cls=strategy_cls,
            )
            self.output_area.delete("1.0", "end")
            self.output_area.insert("end", report_text)
        except ValueError as ve:
            messagebox.showwarning("Input Error", str(ve))
        except Exception as ex:
            messagebox.showerror("Error", str(ex))

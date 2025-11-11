import os
import pandas as pd
import mplfinance as mpf
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
import logging
import matplotlib.pyplot as plt

from utils.symbol_resolver import SymbolResolver

logger = logging.getLogger(__name__)

class MarketStructureAnalyzer:
    def __init__(self, symbol, output_dir="output/reports"):
        self.symbol = symbol
        self.resolver = SymbolResolver()
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def fetch_data(self, days=180):
        """Fetch OHLC data for analysis"""
        df = self.resolver.get_symbol_data(self.symbol, days=days)
        df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        return df

    def identify_structure(self, df):
        """Simple pivot-based structure analysis"""
        df['swing_high'] = (df['high'] > df['high'].shift(1)) & (df['high'] > df['high'].shift(-1))
        df['swing_low'] = (df['low'] < df['low'].shift(1)) & (df['low'] < df['low'].shift(-1))
        df['trend'] = None
        trend = None
        for i in range(2, len(df)):
            if df['swing_high'].iloc[i]:
                trend = 'down'
            elif df['swing_low'].iloc[i]:
                trend = 'up'
            df.at[df.index[i], 'trend'] = trend
        return df

    def generate_chart(self, df):
        chart_path = os.path.join(self.output_dir, f"{self.symbol}_market_structure.png")
        mpf.plot(df, type='candle', style='charles',
                 title=f"{self.symbol} Market Structure",
                 volume=True, savefig=chart_path)
        logger.info(f"Chart saved: {chart_path}")
        return chart_path

    def generate_pdf(self, df):
        pdf_path = os.path.join(self.output_dir, f"{self.symbol}_market_structure_report.pdf")
        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        styles = getSampleStyleSheet()
        content = []

        content.append(Paragraph(f"<b>Market Structure Analysis - {self.symbol}</b>", styles["Heading1"]))
        content.append(Spacer(1, 12))
        content.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))

        recent_trend = df['trend'].iloc[-1]
        last_close = df['close'].iloc[-1]
        content.append(Spacer(1, 12))
        content.append(Paragraph(f"Recent Trend: <b>{recent_trend.upper()}</b>", styles["Normal"]))
        content.append(Paragraph(f"Last Close Price: ₹{last_close:.2f}", styles["Normal"]))
        content.append(Paragraph(f"Swing Highs: {df['swing_high'].sum()} | Swing Lows: {df['swing_low'].sum()}", styles["Normal"]))
        doc.build(content)

        logger.info(f"PDF saved: {pdf_path}")
        return pdf_path

    def run_analysis(self):
        try:
            df = self.fetch_data()
            df = self.identify_structure(df)
            chart_path = self.generate_chart(df)
            pdf_path = self.generate_pdf(df)
            logger.info("Market structure analysis complete")
            return {"pdf": pdf_path, "chart": chart_path}
        except Exception as e:
            logger.error(f"Error in MarketStructureAnalyzer: {e}", exc_info=True)
            raise

# reports/TradeFriendInitialScanPdfGenerator.py

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os

class TradeFriendInitialScanPdfGenerator:

    def generate(
        self,
        scan_date: str,
        rows: list,
        score_cutoff: int,
        output_path: str
    ):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        c = canvas.Canvas(output_path, pagesize=A4)
        width, height = A4
        y = height - 40

        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, y, f"TradeFriend Daily Scan Report — {scan_date}")
        y -= 30

        c.setFont("Helvetica", 10)

        if not rows:
            c.drawString(40, y, "No qualifying stocks found.")
        else:
            for r in rows:
                raw_score = r.get("score")

                score = int(raw_score) if isinstance(raw_score, (int, float)) else 0

                if score < score_cutoff:
                    continue

                line = (
                    f"{r['symbol']} | {r['strategy']} | {r['bias']} | "
                    f"Score: {r['score']} | "
                    f"E:{r['entry']} SL:{r['sl']} T:{r['target']}"
                )
                c.drawString(40, y, line)
                y -= 14

                if y < 40:
                    c.showPage()
                    y = height - 40

        c.save()


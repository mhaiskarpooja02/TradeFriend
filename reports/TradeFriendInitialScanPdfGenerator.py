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
        # ✅ Safely create directory only if present
        folder = os.path.dirname(output_path)
        if folder:
            os.makedirs(folder, exist_ok=True)

        c = canvas.Canvas(output_path, pagesize=A4)
        width, height = A4
        y = height - 40

        # ✅ Title
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, y, f"TradeFriend Daily Scan Report — {scan_date}")
        y -= 30

        c.setFont("Helvetica", 10)

        printed_any = False  # ✅ track if anything is printed

        if not rows:
            c.drawString(40, y, "No qualifying stocks found.")
            printed_any = True
        else:
            for r in rows:
                raw_score = r.get("score")

                try:
                    score = int(float(raw_score))
                except (TypeError, ValueError):
                    score = 0

                if score < score_cutoff:
                    continue

                printed_any = True

                line = (
                    f"{r.get('symbol','-')} | "
                    f"{r.get('strategy','-')} | "
                    f"{r.get('bias','-')} | "
                    f"Score: {score} | "
                    f"E:{r.get('entry','-')} "
                    f"SL:{r.get('sl','-')} "
                    f"T:{r.get('target','-')}"
                )

                c.drawString(40, y, line)
                y -= 14

                if y < 40:
                    c.showPage()
                    c.setFont("Helvetica", 10)
                    y = height - 40

        # ✅ Prevent blank PDF
        if not printed_any:
            c.drawString(40, y, "No stocks met the score cutoff criteria.")

        c.save()

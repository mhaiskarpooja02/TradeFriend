import os
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors


class MorningConfirmPdfBuilder:

    def build(self, report):
        os.makedirs("reports/morning_confirm", exist_ok=True)

        filename = (
            f"reports/morning_confirm/"
            f"morning_confirm_{datetime.now():%Y%m%d_%H%M}.pdf"
        )

        doc = SimpleDocTemplate(
            filename,
            pagesize=A4,
            rightMargin=20,
            leftMargin=20,
            topMargin=20,
            bottomMargin=20
        )

        styles = getSampleStyleSheet()
        normal = styles["Normal"]
        title = styles["Title"]

        elements = []

        # -------------------------
        # HEADER
        # -------------------------
        elements.append(Paragraph("Morning Confirm Report", title))
        elements.append(Spacer(1, 8))

        elements.append(
            Paragraph(
                f"<b>Mode:</b> {report.mode} &nbsp;&nbsp; "
                f"<b>Capital:</b> ₹{report.capital}",
                normal
            )
        )

        elements.append(
            Paragraph(
                f"<b>Generated at:</b> {datetime.now():%Y-%m-%d %H:%M}",
                normal
            )
        )

        elements.append(Spacer(1, 14))

        # -------------------------
        # TABLE HEADER
        # -------------------------
        data = [[
            "Symbol", "LTP", "Entry", "SL", "Target",
            "Decision", "Reason", "Qty", "Pos Value", "Conf"
        ]]

        # -------------------------
        # TABLE ROWS (WRAPPED TEXT)
        # -------------------------
        for r in report.rows:
            data.append([
                r.get("symbol", ""),
                r.get("ltp", ""),
                r.get("entry", ""),
                r.get("sl", ""),
                r.get("target", ""),
                r.get("decision", ""),
                Paragraph(str(r.get("reason", "")), normal),  # ✅ WRAP TEXT
                r.get("qty", ""),
                r.get("position_value", ""),
                r.get("confidence") if r.get("confidence") is not None else "-"
            ])

        # -------------------------
        # TABLE LAYOUT
        # -------------------------
        table = Table(
            data,
            repeatRows=1,
            colWidths=[
                70,   # Symbol
                43,   # LTP
                43,   # Entry
                43,   # SL
                43,   # Target
                55,   # Decision
                160,  # Reason (WIDE + WRAP)
                35,   # Qty
                55,   # Pos Value
                35    # Conf
            ]
        )

        table.setStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ])

        elements.append(table)

        doc.build(elements)
        return filename

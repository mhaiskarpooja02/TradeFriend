import os
from datetime import datetime
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    Paragraph,
    Spacer
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors


class MorningConfirmPdfBuilder:
    """
    PURPOSE:
    - Generate focused Morning Confirm PDFs
    - One PDF per decision type (APPROVED / SKIPPED / REJECTED)
    - No business logic, reporting only
    """

    def build(
        self,
        *,
        title: str,
        rows: list,
        filename_suffix: str,
        mode: str = "",
        capital: float = 0.0
    ) -> str:
        """
        Build a single-purpose Morning Confirm PDF.

        :param title: Report title (shown in PDF)
        :param rows: Filtered decision rows
        :param filename_suffix: approved / skipped / rejected
        :param mode: PAPER / LIVE
        :param capital: Capital used for confirmation
        """

        if not rows:
            return ""

        os.makedirs("reports/morning_confirm", exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = (
            f"reports/morning_confirm/"
            f"morning_confirm_{timestamp}_{filename_suffix}.pdf"
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
        title_style = styles["Title"]

        elements = []

        # -------------------------
        # HEADER
        # -------------------------
        elements.append(Paragraph(title, title_style))
        elements.append(Spacer(1, 8))

        if mode or capital:
            elements.append(
                Paragraph(
                    f"<b>Mode:</b> {mode or '-'} &nbsp;&nbsp; "
                    f"<b>Capital:</b> ₹{capital or '-'}",
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
        # TABLE ROWS
        # -------------------------
        for r in rows:
            data.append([
                r.get("symbol", ""),
                r.get("ltp", "-"),
                r.get("entry", "-"),
                r.get("sl", "-"),
                r.get("target", "-"),
                r.get("decision", ""),
                Paragraph(str(r.get("reason", "")), normal),
                r.get("qty", "-"),
                r.get("position_value", "-"),
                r.get("confidence") if r.get("confidence") is not None else "-"
            ])

        # -------------------------
        # TABLE LAYOUT
        # -------------------------
        table = Table(
            data,
            repeatRows=1,
            colWidths=[
                65,   # Symbol
                40,   # LTP
                40,   # Entry
                40,   # SL
                45,   # Target
                55,   # Decision
                170,  # Reason (wrapped)
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

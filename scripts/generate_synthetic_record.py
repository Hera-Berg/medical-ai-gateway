"""
Generates the SYNTHETIC patient summary PDF used by the seed script.

Everything here is fabricated. The document is deliberately stamped as synthetic
in multiple places (title, header band, footer on every page) so that even a
single chunk surfacing in isolation in the RAG trace is obviously not real PHI.

The content is chosen to PAIR with the authoritative diabetes guidelines so the
cross-corpus comparison demo has something to compare:
  • an HbA1c trend that sits above the guideline target (53 mmol/mol / 7%)
  • a current medication (metformin) that maps to the guideline's first-line rec
  • comorbidities/history that the guideline's individualisation advice touches
"""
from __future__ import annotations

import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _synthetic_band(canvas, doc):
    """Draw a 'SYNTHETIC' band + footer on every page."""
    canvas.saveState()
    # top band
    canvas.setFillColor(colors.HexColor("#FDE8E8"))
    canvas.rect(0, A4[1] - 16 * mm, A4[0], 16 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#B91C1C"))
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawCentredString(
        A4[0] / 2,
        A4[1] - 10 * mm,
        "SYNTHETIC RECORD — NOT A REAL PATIENT — FOR DEMONSTRATION ONLY",
    )
    # footer
    canvas.setFillColor(colors.HexColor("#9CA3AF"))
    canvas.setFont("Helvetica", 7)
    canvas.drawCentredString(
        A4[0] / 2,
        8 * mm,
        "Synthetic demonstration data generated for the Medical AI Gateway. "
        "Not medical advice. Page %d" % doc.page,
    )
    canvas.restoreState()


def build(path: str) -> None:
    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        topMargin=22 * mm,
        bottomMargin=16 * mm,
        title="Synthetic Patient Summary (Demo)",
        author="Medical AI Gateway — synthetic data generator",
    )
    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Heading2"], textColor=colors.HexColor("#1F2937"))
    body = styles["BodyText"]
    small = ParagraphStyle("small", parent=body, fontSize=9, textColor=colors.HexColor("#374151"))

    story = []

    story.append(Paragraph("Synthetic Patient Summary", styles["Title"]))
    story.append(
        Paragraph(
            "<b>This is fabricated data for software demonstration.</b> The person "
            "described does not exist. Values were invented to exercise a "
            "retrieval-augmented generation demo and must never be used for any "
            "clinical purpose.",
            small,
        )
    )
    story.append(Spacer(1, 8))

    # Demographics (obviously fake)
    demo = [
        ["Name", "Pat Sample (FICTIONAL)"],
        ["Record ID", "SYNTH-0001"],
        ["Date of birth", "01 Jan 1970 (synthetic)"],
        ["Sex", "Not specified"],
        ["Primary condition", "Type 2 diabetes mellitus (synthetic)"],
    ]
    t = Table(demo, colWidths=[40 * mm, 110 * mm])
    t.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6B7280")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#E5E7EB")),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 12))

    # History
    story.append(Paragraph("Relevant history", h))
    story.append(
        Paragraph(
            "Type 2 diabetes diagnosed (synthetic) approximately 6 years ago. "
            "Hypertension, managed. No known established cardiovascular disease. "
            "No history of severe hypoglycaemia. Non-smoker. Family history of "
            "type 2 diabetes. All details fabricated for demonstration.",
            body,
        )
    )
    story.append(Spacer(1, 8))

    # Current medications — chosen to map onto guideline first-line therapy
    story.append(Paragraph("Current medications (synthetic)", h))
    meds = [
        ["Medication", "Dose", "Notes"],
        ["Metformin", "1000 mg twice daily", "First-line agent; tolerated"],
        ["Perindopril", "5 mg daily", "For blood pressure"],
        ["Atorvastatin", "20 mg daily", "Lipid management"],
    ]
    mt = Table(meds, colWidths=[45 * mm, 45 * mm, 60 * mm])
    mt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2FF")),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
                ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(mt)
    story.append(Spacer(1, 12))

    # Lab results — HbA1c trend ABOVE the guideline target, to drive comparison
    story.append(Paragraph("Recent laboratory results (synthetic)", h))
    story.append(
        Paragraph(
            "HbA1c trend over the past 12 months (fabricated). The guideline "
            "target referenced in the authoritative corpus is 53 mmol/mol (7%); "
            "these synthetic values sit above target, which is the point of the "
            "demonstration comparison.",
            small,
        )
    )
    story.append(Spacer(1, 4))
    labs = [
        ["Date (synthetic)", "Test", "Result", "Reference"],
        ["12 months ago", "HbA1c", "75 mmol/mol (9.0%)", "Target 53 mmol/mol (7%)"],
        ["6 months ago", "HbA1c", "68 mmol/mol (8.4%)", "Target 53 mmol/mol (7%)"],
        ["Most recent", "HbA1c", "61 mmol/mol (7.7%)", "Target 53 mmol/mol (7%)"],
        ["Most recent", "eGFR", "82 mL/min/1.73m2", ">= 60 normal"],
        ["Most recent", "Blood pressure", "134/82 mmHg", "< 140/90"],
    ]
    lt = Table(labs, colWidths=[35 * mm, 30 * mm, 45 * mm, 50 * mm])
    lt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FEF3C7")),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
                ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(lt)
    story.append(Spacer(1, 12))

    # A plain-language note that invites cross-corpus questions
    story.append(Paragraph("Summary note (synthetic)", h))
    story.append(
        Paragraph(
            "Synthetic patient with type 2 diabetes whose most recent HbA1c "
            "(61 mmol/mol, 7.7%) remains above the guideline target despite "
            "metformin. Renal function and blood pressure are within acceptable "
            "synthetic ranges. This record is intended to be compared against "
            "published guidance to illustrate cross-corpus retrieval — for "
            "example, whether intensification of glucose-lowering therapy would "
            "be consistent with the authoritative recommendations. Entirely "
            "fabricated; not clinical advice.",
            body,
        )
    )

    doc.build(story, onFirstPage=_synthetic_band, onLaterPages=_synthetic_band)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "synthetic_patient_summary.pdf"
    build(out)
    print(f"wrote {out}")

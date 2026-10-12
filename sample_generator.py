"""
Sample Third-Party Lab PDF Generator.
Uses ReportLab to generate a realistic raw 3rd-party lab report PDF for immediate testing.
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_sample_pdf(output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    normal_style = styles['Normal']

    title_style = ParagraphStyle(
        'ThirdPartyTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#1e3a8a')
    )
    
    meta_style = ParagraphStyle(
        'MetaStyle',
        parent=normal_style,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155')
    )

    story = []

    # Third Party Header
    story.append(Paragraph("<b>GLOBAL PATHOLOGY LABS & DIAGNOSTICS INC.</b>", title_style))
    story.append(Paragraph("Branch: Central Referral Laboratory | Reg: GPL-7821-X", meta_style))
    story.append(Spacer(1, 10))

    # Patient Details Table
    patient_data = [
        [
            Paragraph("<b>Patient Name:</b> Rajesh Kumar", meta_style),
            Paragraph("<b>Sample ID:</b> GPL-2026-90412", meta_style)
        ],
        [
            Paragraph("<b>Age/Gender:</b> 45 Yrs / Male", meta_style),
            Paragraph("<b>Referred By:</b> Dr. S. N. Mukherjee, MD", meta_style)
        ],
        [
            Paragraph("<b>Collection Date:</b> 22/09/2026 08:30 AM", meta_style),
            Paragraph("<b>Report Date:</b> 22/09/2026 04:15 PM", meta_style)
        ]
    ]

    patient_table = Table(patient_data, colWidths=[270, 270])
    patient_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#94a3b8')),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(patient_table)
    story.append(Spacer(1, 15))

    # Test Results Table
    header_style = ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white)
    cell_style = ParagraphStyle('TD', fontName='Helvetica', fontSize=8.5, leading=11)
    bold_cell_style = ParagraphStyle('TDBold', fontName='Helvetica-Bold', fontSize=8.5, leading=11)

    table_data = [
        [
            Paragraph("<b>Test Investigation</b>", header_style),
            Paragraph("<b>Observed Result</b>", header_style),
            Paragraph("<b>Units</b>", header_style),
            Paragraph("<b>Reference Interval</b>", header_style)
        ],
        # CBC Panel
        [Paragraph("<b>COMPLETE BLOOD COUNT (CBC)</b>", bold_cell_style), "", "", ""],
        [Paragraph("Hemoglobin (Hb)", cell_style), Paragraph("11.8", bold_cell_style), Paragraph("g/dL", cell_style), Paragraph("13.0 - 17.0", cell_style)],
        [Paragraph("RBC Count", cell_style), Paragraph("4.10", cell_style), Paragraph("10^6/uL", cell_style), Paragraph("4.50 - 5.50", cell_style)],
        [Paragraph("PCV / Hematocrit", cell_style), Paragraph("37.2", cell_style), Paragraph("%", cell_style), Paragraph("40.0 - 50.0", cell_style)],
        [Paragraph("MCV", cell_style), Paragraph("85.4", cell_style), Paragraph("fL", cell_style), Paragraph("80.0 - 100.0", cell_style)],
        [Paragraph("Total WBC Count (TLC)", cell_style), Paragraph("11800", bold_cell_style), Paragraph("/cu.mm", cell_style), Paragraph("4000 - 11000", cell_style)],
        [Paragraph("Platelet Count", cell_style), Paragraph("280", cell_style), Paragraph("10^3/uL", cell_style), Paragraph("150 - 450", cell_style)],
        # Lipid Panel
        [Paragraph("<b>LIPID PROFILE</b>", bold_cell_style), "", "", ""],
        [Paragraph("Total Cholesterol", cell_style), Paragraph("235.0", bold_cell_style), Paragraph("mg/dL", cell_style), Paragraph("< 200", cell_style)],
        [Paragraph("Triglycerides", cell_style), Paragraph("185.0", bold_cell_style), Paragraph("mg/dL", cell_style), Paragraph("< 150", cell_style)],
        [Paragraph("HDL Cholesterol", cell_style), Paragraph("38.0", cell_style), Paragraph("mg/dL", cell_style), Paragraph("40.0 - 60.0", cell_style)],
        [Paragraph("LDL Cholesterol", cell_style), Paragraph("160.0", bold_cell_style), Paragraph("mg/dL", cell_style), Paragraph("< 100", cell_style)],
        # Liver Function Panel
        [Paragraph("<b>LIVER FUNCTION TEST (LFT)</b>", bold_cell_style), "", "", ""],
        [Paragraph("Bilirubin Total", cell_style), Paragraph("0.9", cell_style), Paragraph("mg/dL", cell_style), Paragraph("0.2 - 1.2", cell_style)],
        [Paragraph("SGPT / ALT", cell_style), Paragraph("58.0", bold_cell_style), Paragraph("U/L", cell_style), Paragraph("10 - 45", cell_style)],
        [Paragraph("SGOT / AST", cell_style), Paragraph("42.0", bold_cell_style), Paragraph("U/L", cell_style), Paragraph("10 - 40", cell_style)],
        # Kidney Function Panel
        [Paragraph("<b>KIDNEY FUNCTION TEST (KFT)</b>", bold_cell_style), "", "", ""],
        [Paragraph("Serum Creatinine", cell_style), Paragraph("1.1", cell_style), Paragraph("mg/dL", cell_style), Paragraph("0.6 - 1.3", cell_style)],
        [Paragraph("Blood Urea", cell_style), Paragraph("28.0", cell_style), Paragraph("mg/dL", cell_style), Paragraph("15.0 - 45.0", cell_style)],
        [Paragraph("Fasting Blood Glucose (FBS)", cell_style), Paragraph("112.0", bold_cell_style), Paragraph("mg/dL", cell_style), Paragraph("70 - 100", cell_style)]
    ]

    results_table = Table(table_data, colWidths=[200, 100, 100, 140])
    results_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (0,8), (-1,8), colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (0,14), (-1,14), colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (0,18), (-1,18), colors.HexColor('#f1f5f9')),
    ]))
    story.append(results_table)

    story.append(Spacer(1, 20))
    story.append(Paragraph("<b>--- END OF 3RD PARTY REPORT ---</b>", ParagraphStyle('End', alignment=1, fontSize=8, textColor=colors.gray)))

    doc.build(story)
    print(f"Sample PDF successfully generated at: {output_path}")

if __name__ == "__main__":
    generate_sample_pdf("sample_data/third_party_lab_report.pdf")

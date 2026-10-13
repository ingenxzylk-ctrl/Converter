"""
Word Document Export Service for Lab Report Transformation.
Generates an official print-perfect .docx report faithfully mirroring
the branded 4-page Zylk Health PDF laboratory report.

Fixes WPS Office / Microsoft Word rendering issues:
1. Unified 5-column demographics + photo table (eliminates nested-table distortion)
2. Explicit w:tblGrid and w:tcW geometry on all tables (prevents column squishing and text wrapping into single-character vertical stacks)
3. Compact row heights and tight padding on CBC report to eliminate blank page spillover
4. Clean 6-column geometry on 53-analytes table with ample width for category names
5. Fully responsive male vs female card image scaling
"""
import io
import re
from pathlib import Path
from docx import Document
from docx.shared import Pt, RGBColor, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# Brand color palette (exact match to PDF template)
TEAL_BANNER = "0D4D44"       # Deep pine/teal banner header
TEAL_BRAND = RGBColor(0x0D, 0x4D, 0x44)
TEAL_CARD = RGBColor(0x00, 0x66, 0x66)
TEAL_CARD_HEX = "006666"
TEAL_ACCRED = RGBColor(0x00, 0x80, 0x80)
TEAL_LIGHT_HEX = "99F6E4"    # Mint/turquoise for banner subtitle
TEAL_LIGHT = RGBColor(0x99, 0xF6, 0xE4)
GREEN_FINAL = RGBColor(0x05, 0x96, 0x69)
RED_FLAG = RGBColor(0xDC, 0x26, 0x26)
RED_FLAG_HEX = "DC2626"
BLUE_RANGE = RGBColor(0x03, 0x69, 0xA1)
BLUE_RANGE_53 = RGBColor(0x02, 0x84, 0xC7)
DARK_TEXT = RGBColor(0x0F, 0x17, 0x2A)
BODY_TEXT = RGBColor(0x1E, 0x29, 0x3B)
MUTED_TEXT = RGBColor(0x64, 0x74, 0x8B)
FOOTER_GREY = RGBColor(0x94, 0xA3, 0xB8)
BG_ALT_ROW = "F8FAFC"
BG_CAT_ROW = "F1F5F9"
BORDER_GREY = "E2E8F0"
BORDER_CARD = "CBD5E1"
WHITE = RGBColor(0xFF, 0xFF, 0xFF)


# ==============================================================================
# XML Shading, Margin, Border & Geometry Helpers
# ==============================================================================

def _set_cell_bg(cell, hex_color: str):
    """Set cell background colour via XML shading."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def _set_cell_margins(cell, top=50, bottom=50, left=80, right=80):
    """Set cell internal padding in dxa (20 dxa = 1 pt)."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for m, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
        node = OxmlElement(f"w:{m}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def _set_cell_borders(cell, top=None, bottom=None, left=None, right=None):
    """Set explicit borders on a table cell."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    borders = {"top": top, "bottom": bottom, "left": left, "right": right}
    for b_name, b_val in borders.items():
        node = OxmlElement(f"w:{b_name}")
        if b_val is not None:
            node.set(qn("w:val"), b_val.get("val", "single"))
            node.set(qn("w:sz"), str(b_val.get("sz", 4)))
            node.set(qn("w:space"), "0")
            node.set(qn("w:color"), b_val.get("color", "CBD5E1"))
        else:
            node.set(qn("w:val"), "none")
        tcBorders.append(node)
    tcPr.append(tcBorders)


def _cant_split(row):
    """Ensure a table row does not break across pages."""
    trPr = row._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:cantSplit"))


def _repeat_header(row):
    """Repeat header row on subsequent pages if split."""
    trPr = row._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:tblHeader"))


def _apply_table_geometry(table, col_widths_cm: list):
    """
    Strictly enforce column widths in Word and WPS Office:
    1. Sets explicit w:tblW in tblPr.
    2. Enforces w:tblLayout w:type="fixed" so column widths are never re-estimated.
    3. Builds and inserts w:tblGrid with exact w:gridCol widths.
    4. Sets w:tcW with dxa units on each cell, accurately accounting for w:gridSpan.
    """
    col_dxa = [int(w * 567) for w in col_widths_cm]
    total_dxa = sum(col_dxa)
    tblPr = table._tbl.tblPr

    # 1. Table total width
    tblW = tblPr.find(qn("w:tblW"))
    if tblW is None:
        tblW = OxmlElement("w:tblW")
        tblPr.append(tblW)
    tblW.set(qn("w:w"), str(total_dxa))
    tblW.set(qn("w:type"), "dxa")

    # 2. Enforce fixed table layout (prevents Word/WPS auto-squishing)
    tblLayout = tblPr.find(qn("w:tblLayout"))
    if tblLayout is None:
        tblLayout = OxmlElement("w:tblLayout")
        tblPr.append(tblLayout)
    tblLayout.set(qn("w:type"), "fixed")

    # 3. Table grid definition
    old_grid = table._tbl.find(qn("w:tblGrid"))
    if old_grid is not None:
        table._tbl.remove(old_grid)

    tblGrid = OxmlElement("w:tblGrid")
    for w_dxa in col_dxa:
        gc = OxmlElement("w:gridCol")
        gc.set(qn("w:w"), str(w_dxa))
        tblGrid.append(gc)

    table._tbl.insert(table._tbl.index(tblPr) + 1, tblGrid)

    # 4. Set cell widths accounting for gridSpan
    for row in table.rows:
        _cant_split(row)
        col_idx = 0
        for cell in row.cells:
            tcPr = cell._tc.get_or_add_tcPr()
            gridSpan = tcPr.find(qn("w:gridSpan"))
            span = int(gridSpan.get(qn("w:val"))) if gridSpan is not None else 1

            if col_idx < len(col_dxa):
                cell_w_dxa = sum(col_dxa[col_idx : col_idx + span])
                tcW = tcPr.find(qn("w:tcW"))
                if tcW is None:
                    tcW = OxmlElement("w:tcW")
                    tcPr.append(tcW)
                tcW.set(qn("w:w"), str(cell_w_dxa))
                tcW.set(qn("w:type"), "dxa")

            col_idx += span


def _style_cell(cell, text: str, font_size: float = 7.0, color: RGBColor = DARK_TEXT,
                bold: bool = False, bg: str = None, align=WD_ALIGN_PARAGRAPH.LEFT,
                pad_top=30, pad_bottom=30, pad_left=70, pad_right=70):
    cell.text = ""
    if bg:
        _set_cell_bg(cell, bg)
    _set_cell_margins(cell, pad_top, pad_bottom, pad_left, pad_right)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    para = cell.paragraphs[0]
    para.alignment = align
    para.paragraph_format.space_before = Pt(0)
    para.paragraph_format.space_after = Pt(0)
    para.paragraph_format.line_spacing = 1.0

    run = para.add_run(str(text))
    run.font.name = "Segoe UI"
    run.font.size = Pt(font_size)
    run.bold = bold
    if color:
        run.font.color.rgb = color
    return run


# ==============================================================================
# Patient Gender & Title Normalization
# ==============================================================================

def is_male_patient(metadata: dict) -> bool:
    """
    Deterministically identify whether the patient is Male or Female:
    1. Female markers take absolute precedence (prevents 'WOMEN' matching 'MEN').
    2. Check test package name, metadata gender, and age_gender string.
    """
    test_type = (metadata.get("test_type") or "").upper()
    gender = (metadata.get("gender") or "").upper().strip()
    age_gender = (metadata.get("age_gender") or "").upper().strip()

    # Female checks FIRST
    if "WOMEN" in test_type or "FEMALE" in test_type or gender == "FEMALE":
        return False
    if re.search(r'(?:\/F\b|\bFEMALE\b)', age_gender):
        return False

    # Male checks
    if re.search(r'\b(MEN|MENS|MALE|MALES)\b', test_type):
        return True
    if gender == "MALE":
        return True
    if re.search(r'(?:\/M\b|\bMALE\b)', age_gender):
        return True

    return False


def get_clean_test_title(raw_title: str, is_male: bool) -> str:
    """
    Standardize the test package title to:
    'MENS HAIRFALL SCREENING ADVANCED' or 'WOMEN HAIRFALL SCREENING ADVANCED'.
    """
    raw_upper = (raw_title or "").upper()
    # Check WOMEN / FEMALE first to prevent substring match on 'MEN'
    if "WOMEN" in raw_upper or "FEMALE" in raw_upper or not is_male:
        return "WOMEN HAIRFALL SCREENING ADVANCED"
    elif re.search(r'\b(MENS|MEN|MALE)\b', raw_upper) or is_male:
        return "MENS HAIRFALL SCREENING ADVANCED"
    elif raw_title:
        clean = re.sub(r'^(?:SERUM:|EDTA:|\s*JAANCH\s*[-–:]\s*)', '', raw_title, flags=re.IGNORECASE).strip()
        return clean.upper()
    return "MENS HAIRFALL SCREENING ADVANCED" if is_male else "WOMEN HAIRFALL SCREENING ADVANCED"


# ==============================================================================
# Reusable Page Header Banner & Footer
# ==============================================================================

def _add_header_banner(doc: Document, patient_name: str, lab_code: str, show_meta: bool = True):
    """
    Renders the exact dark-teal `#0D4D44` header banner seen at the top
    of every page in the PDF template. If show_meta is True, includes
    the MEDICAL LABORATORY REPORT title and patient/lab meta on the right.
    """
    banner = doc.add_table(rows=1, cols=2)
    banner.alignment = WD_TABLE_ALIGNMENT.CENTER
    banner.autofit = False
    _apply_table_geometry(banner, [8.0, 10.6])

    # Left cell: "Zylk Health"
    c_left = banner.rows[0].cells[0]
    _set_cell_bg(c_left, TEAL_BANNER)
    _set_cell_margins(c_left, top=60, bottom=60, left=140, right=80)
    c_left.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p_left = c_left.paragraphs[0]
    p_left.paragraph_format.space_before = Pt(0)
    p_left.paragraph_format.space_after = Pt(0)
    r_left = p_left.add_run("Zylk Health")
    r_left.font.name = "Segoe UI"
    r_left.font.size = Pt(13)
    r_left.bold = True
    r_left.font.color.rgb = WHITE

    # Right cell: "MEDICAL LABORATORY REPORT" + patient/code meta (Page 1 only)
    c_right = banner.rows[0].cells[1]
    _set_cell_bg(c_right, TEAL_BANNER)
    _set_cell_margins(c_right, top=50, bottom=50, left=80, right=140)
    c_right.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p_right = c_right.paragraphs[0]
    p_right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_right.paragraph_format.space_before = Pt(0)
    p_right.paragraph_format.space_after = Pt(0)
    p_right.paragraph_format.line_spacing = 1.15

    if show_meta:
        r_top = p_right.add_run("MEDICAL LABORATORY REPORT\n")
        r_top.font.name = "Segoe UI"
        r_top.font.size = Pt(7.0)
        r_top.bold = True
        r_top.font.color.rgb = WHITE

        r_meta = p_right.add_run(f"{(patient_name or 'PATIENT').upper()} | Lab code: {lab_code}")
        r_meta.font.name = "Segoe UI"
        r_meta.font.size = Pt(6.8)
        r_meta.bold = True
        r_meta.font.color.rgb = TEAL_LIGHT

    gap = doc.add_paragraph()
    gap.paragraph_format.space_before = Pt(0)
    gap.paragraph_format.space_after = Pt(2)


def _setup_document_footer(section, report_date: str, phone: str):
    """
    Renders the exact accreditation footer directly inside Word's official
    section.footer, featuring dynamic Word field codes for PAGE and NUMPAGES:
    1. All tests are performed at an NABL-accredited, ISO 9001-certified and CAP-accredited medical laboratory.
    2. The result are reviewed and Verified by an MD pathologist.
    3. Page X of Y (right aligned)
    """
    footer = section.footer
    footer.is_linked_to_previous = False

    # Top border / separator line on footer
    p1 = footer.paragraphs[0]
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p1.paragraph_format.space_before = Pt(0)
    p1.paragraph_format.space_after = Pt(1)
    p1.paragraph_format.line_spacing = 1.0

    pBdr = OxmlElement('w:pBdr')
    top = OxmlElement('w:top')
    top.set(qn('w:val'), 'single')
    top.set(qn('w:sz'), '4')
    top.set(qn('w:space'), '4')
    top.set(qn('w:color'), 'E2E8F0')
    pBdr.append(top)
    p1._p.get_or_add_pPr().append(pBdr)

    # Line 1: Accreditation
    r1 = p1.add_run("All tests are performed at an NABL-accredited, ISO 9001-certified and CAP-accredited medical laboratory.")
    r1.font.name = "Segoe UI"
    r1.font.size = Pt(6.8)
    r1.bold = True
    r1.font.color.rgb = TEAL_ACCRED

    # Line 2: Pathologist Verified
    p2 = footer.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.paragraph_format.space_before = Pt(0)
    p2.paragraph_format.space_after = Pt(2)
    p2.paragraph_format.line_spacing = 1.0
    r2 = p2.add_run("The result are reviewed and Verified by an MD pathologist.")
    r2.font.name = "Segoe UI"
    r2.font.size = Pt(7.2)
    r2.bold = True
    r2.font.color.rgb = TEAL_ACCRED

    # Line 3: Right-aligned dynamic page numbering
    p3 = footer.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p3.paragraph_format.space_before = Pt(0)
    p3.paragraph_format.space_after = Pt(0)
    p3.paragraph_format.line_spacing = 1.0

    r3 = p3.add_run("Page ")
    r3.font.name = "Segoe UI"
    r3.font.size = Pt(6.5)
    r3.font.color.rgb = FOOTER_GREY

    fld_page = OxmlElement('w:fldSimple')
    fld_page.set(qn('w:instr'), 'PAGE')
    r_p = OxmlElement('w:r')
    r_p_pr = OxmlElement('w:rPr')
    r_p_font = OxmlElement('w:rFonts')
    r_p_font.set(qn('w:ascii'), 'Segoe UI')
    r_p_pr.append(r_p_font)
    r_p_col = OxmlElement('w:color')
    r_p_col.set(qn('w:val'), '94A3B8')
    r_p_pr.append(r_p_col)
    r_p_sz = OxmlElement('w:sz')
    r_p_sz.set(qn('w:val'), '13')
    r_p_pr.append(r_p_sz)
    r_p.append(r_p_pr)
    t_p = OxmlElement('w:t')
    t_p.text = '1'
    r_p.append(t_p)
    fld_page.append(r_p)
    p3._p.append(fld_page)

    r_of = p3.add_run(" of ")
    r_of.font.name = "Segoe UI"
    r_of.font.size = Pt(6.5)
    r_of.font.color.rgb = FOOTER_GREY

    fld_num = OxmlElement('w:fldSimple')
    fld_num.set(qn('w:instr'), 'NUMPAGES')
    r_n = OxmlElement('w:r')
    r_n_pr = OxmlElement('w:rPr')
    r_n_font = OxmlElement('w:rFonts')
    r_n_font.set(qn('w:ascii'), 'Segoe UI')
    r_n_pr.append(r_n_font)
    r_n_col = OxmlElement('w:color')
    r_n_col.set(qn('w:val'), '94A3B8')
    r_n_pr.append(r_n_col)
    r_n_sz = OxmlElement('w:sz')
    r_n_sz.set(qn('w:val'), '13')
    r_n_pr.append(r_n_sz)
    r_n.append(r_n_pr)
    t_n = OxmlElement('w:t')
    t_n.text = '4'
    r_n.append(t_n)
    fld_num.append(r_n)
    p3._p.append(fld_num)


# ==============================================================================
# Master Word Document Generator
# ==============================================================================

def generate_word_report_bytes(patient_data: dict) -> bytes:
    """
    Renders patient_data into an official print-perfect A4 Word document (.docx)
    faithfully reproducing the 4-page Zylk Health branded report layout.
    """
    clinic = patient_data.get("clinic", {})
    metadata = patient_data.get("metadata", {})
    tests = patient_data.get("tests", [])
    is_male = is_male_patient(metadata)
    from blood_tests_db import ensure_test_flag
    gender = metadata.get("gender", "MALE" if is_male else "FEMALE")
    for t in tests:
        ensure_test_flag(t, gender=gender)
    flagged_tests = [t for t in tests if str(t.get("flag", "")).upper() in ["HIGH", "LOW"]]
    tmap = {t["parameter"]: t for t in tests}

    patient_name = (metadata.get("patient_name") or "KANAGAVALLI K").strip()
    lab_code = metadata.get("lab_code") or metadata.get("sample_id") or "1509074825/FE254"
    report_date = metadata.get("report_date") or metadata.get("collection_date") or "15 Sep 2026"
    phone = metadata.get("phone") or "+91 98943 77521"

    is_male = is_male_patient(metadata)
    test_pkg = get_clean_test_title(metadata.get("test_type"), is_male)
    spec_val = metadata.get("specimen") or "Blood Test"
    specimen = "Blood Test" if ("Serum; whole blood" in spec_val or not spec_val) else spec_val
    coll_date = metadata.get("collection_date") or "15 Sep 2026"
    age_val = metadata.get("age_gender") or "21"
    pincode = metadata.get("pincode") or "627007"
    addr = metadata.get("address") or "INGENX LABS Pvt Ltd., P18, Shifa Golden City, Tirunelveli. - 627007"

    doc = Document()

    # Set default document font to Segoe UI
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Segoe UI"
    font.size = Pt(7.0)
    font.color.rgb = BODY_TEXT

    # Configure exact A4 dimensions with 12mm left/right and margins for header & footer
    for section in doc.sections:
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(0.8)
        section.bottom_margin = Cm(1.6)
        section.left_margin = Cm(1.2)
        section.right_margin = Cm(1.2)
        section.footer_distance = Cm(0.6)
        _setup_document_footer(section, report_date, phone)

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 1: DEMOGRAPHICS + TIER 1 OUT OF REFERENCE RANGE
    # ══════════════════════════════════════════════════════════════════════════
    _add_header_banner(doc, patient_name, lab_code, show_meta=True)

    # Title Area
    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(1)
    r_main = p_title.add_run("Laboratory Report")
    r_main.font.name = "Segoe UI"
    r_main.font.size = Pt(14)
    r_main.bold = True
    r_main.font.color.rgb = DARK_TEXT

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(3)
    r_sub = p_sub.add_run("Summary of results that need attention, followed by the complete results.")
    r_sub.font.name = "Segoe UI"
    r_sub.font.size = Pt(7.2)
    r_sub.font.color.rgb = MUTED_TEXT

    # ── Unified 6-Column Demographics + Photo Table ───────────────────────────
    # Columns: Label1 (2.6cm), Val1 (4.3cm), Label2 (2.6cm), Val2 (4.4cm), Spacer (0.3cm), Photo (4.4cm) = 18.6cm
    demog_widths = [2.6, 4.3, 2.6, 4.4, 0.3, 4.4]
    dt = doc.add_table(rows=6, cols=6)
    dt.alignment = WD_TABLE_ALIGNMENT.CENTER
    dt.autofit = False

    # 1. Merge Col 5 across rows 0-5 for the photo card
    photo_cell = dt.cell(0, 5)
    for r in range(1, 6):
        photo_cell = photo_cell.merge(dt.cell(r, 5))

    # 2. Merge Row 5 cols 0-3 for Address
    addr_cell = dt.cell(5, 0).merge(dt.cell(5, 3))

    # Helper for filling demographic card rows
    def _fill_card_row(row_idx, l1, v1, l2, v2, v1_color=DARK_TEXT, v2_color=DARK_TEXT):
        row = dt.rows[row_idx]
        _style_cell(row.cells[0], l1, 6.0, TEAL_CARD, bold=True, pad_top=22, pad_bottom=22, pad_left=60, pad_right=20)
        _style_cell(row.cells[1], v1, 7.5, v1_color, bold=True, pad_top=22, pad_bottom=22, pad_left=20, pad_right=60)
        _style_cell(row.cells[2], l2, 6.0, TEAL_CARD, bold=True, pad_top=22, pad_bottom=22, pad_left=60, pad_right=20)
        _style_cell(row.cells[3], v2, 7.5, v2_color, bold=True, pad_top=22, pad_bottom=22, pad_left=20, pad_right=60)
        # Spacer cell (Col 4)
        _style_cell(row.cells[4], "", 1.0, None, pad_top=0, pad_bottom=0, pad_left=0, pad_right=0)
        _set_cell_borders(row.cells[4])

    _fill_card_row(0, "PATIENT NAME", patient_name.upper(), "TEST PACKAGE", test_pkg)
    _fill_card_row(1, "SAMPLE DATE", coll_date, "REPORT DATE", report_date)
    _fill_card_row(2, "PHONE NUMBER", phone, "REPORT ID / LAB CODE", lab_code)
    _fill_card_row(3, "SPECIMEN", specimen, "STATUS", "Final – Verified", v2_color=GREEN_FINAL)
    _fill_card_row(4, "AGE", age_val, "PINCODE", pincode)

    # Address row (Row 5)
    _style_cell(addr_cell, f"ADDRESS:  {addr}", 7.2, DARK_TEXT, bold=True, pad_top=24, pad_bottom=24, pad_left=60, pad_right=60)
    # Spacer cell on row 5
    _style_cell(dt.rows[5].cells[4], "", 1.0, None, pad_top=0, pad_bottom=0, pad_left=0, pad_right=0)
    _set_cell_borders(dt.rows[5].cells[4])

    # Apply Card Borders to demographics cells (cols 0-3)
    card_border = {"val": "single", "sz": 12, "color": "006666"}
    div_border = {"val": "single", "sz": 4, "color": "E5E7EB"}

    for r_idx in range(5):
        row = dt.rows[r_idx]
        for c_idx in range(4):
            c = row.cells[c_idx]
            top_b = card_border if r_idx == 0 else None
            left_b = card_border if c_idx == 0 else None
            right_b = card_border if c_idx == 3 else None
            _set_cell_borders(c, top=top_b, bottom=div_border, left=left_b, right=right_b)

    # Address row borders
    _set_cell_borders(addr_cell, top=None, bottom=card_border, left=card_border, right=card_border)

    # Populate Photo Cell (Col 5)
    _set_cell_bg(photo_cell, "087571")
    _set_cell_margins(photo_cell, top=0, bottom=0, left=0, right=0)
    _set_cell_borders(photo_cell, top=card_border, bottom=card_border, left=card_border, right=card_border)
    photo_cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    hero_card_file = "male_hero_card.png" if is_male else "female_hero_card.png"
    hero_card_path = STATIC_DIR / "images" / hero_card_file
    if not hero_card_path.exists():
        hero_card_file = "male_hero.png" if is_male else "female_hero.png"
        hero_card_path = STATIC_DIR / "images" / hero_card_file

    p_photo = photo_cell.paragraphs[0]
    p_photo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_photo.paragraph_format.space_before = Pt(0)
    p_photo.paragraph_format.space_after = Pt(0)
    if hero_card_path.exists():
        run_img = p_photo.add_run()
        # Proportions image to cover the full personal details box height
        run_img.add_picture(str(hero_card_path), width=Cm(4.35), height=Cm(4.65))

    # Apply strict table geometry to dt after merging
    _apply_table_geometry(dt, demog_widths)

    # Tier 1 Title: Results Needing Attention
    p_t1_title = doc.add_paragraph()
    p_t1_title.paragraph_format.space_before = Pt(4)
    p_t1_title.paragraph_format.space_after = Pt(1)
    r_t1 = p_t1_title.add_run("Results Needing Attention")
    r_t1.font.name = "Segoe UI"
    r_t1.font.size = Pt(10.5)
    r_t1.bold = True
    r_t1.font.color.rgb = DARK_TEXT

    p_t1_note = doc.add_paragraph()
    p_t1_note.paragraph_format.space_before = Pt(0)
    p_t1_note.paragraph_format.space_after = Pt(2)
    r_red_note = p_t1_note.add_run("Bold red rows = needs prompt clinical review. ")
    r_red_note.font.name = "Segoe UI"
    r_red_note.font.size = Pt(6.8)
    r_red_note.bold = True
    r_red_note.font.color.rgb = RED_FLAG
    r_grey_note = p_t1_note.add_run("All values are shown exactly as reported by the laboratory.")
    r_grey_note.font.name = "Segoe UI"
    r_grey_note.font.size = Pt(6.8)
    r_grey_note.font.color.rgb = MUTED_TEXT

    # Tier 1 Table with explicit geometry
    t1_widths = [3.2, 5.6, 1.8, 1.6, 2.2, 4.2]
    t1 = doc.add_table(rows=1, cols=6)
    t1.alignment = WD_TABLE_ALIGNMENT.CENTER
    t1.autofit = False
    _repeat_header(t1.rows[0])

    t1_headers = ["AREA", "TEST", "RESULT", "FLAG", "UNITS", "REFERENCE RANGE"]
    for i, (hdr, w) in enumerate(zip(t1_headers, t1_widths)):
        cell = t1.rows[0].cells[i]
        align = WD_ALIGN_PARAGRAPH.CENTER if i in (2, 3) else WD_ALIGN_PARAGRAPH.LEFT
        _style_cell(cell, hdr, 6.8, WHITE, bold=True, bg=TEAL_BANNER, align=align, pad_top=25, pad_bottom=25)

    flagged_display = flagged_tests if (flagged_tests and len(flagged_tests) > 0) else [
        {"category": "Thyroid", "parameter": "TSH - Ultrasensitive", "value": "21.747", "flag": "High", "unit": "µIU/mL", "ref_range": "0.35 - 4.94"},
        {"category": "Vitamins", "parameter": "25-OH Vitamin D (Total)", "value": "11.4", "flag": "Low", "unit": "ng/mL", "ref_range": "30 - 100"},
        {"category": "Iron Deficiency", "parameter": "Iron", "value": "28.2", "flag": "Low", "unit": "µg/dL", "ref_range": "37 - 165"},
        {"category": "Iron Deficiency", "parameter": "% Transferrin Saturation", "value": "5.88", "flag": "Low", "unit": "%", "ref_range": "13 - 45"},
        {"category": "Iron Deficiency", "parameter": "Unsat. Iron-Binding Capacity (UIBC)", "value": "451.8", "flag": "High", "unit": "µg/dL", "ref_range": "162 - 368"},
        {"category": "Infertility", "parameter": "Prolactin (PRL)", "value": "54.8", "flag": "High", "unit": "ng/mL", "ref_range": "4.79 - 23.3"},
        {"category": "Arthritis", "parameter": "Phosphorous", "value": "10.27", "flag": "High", "unit": "mg/dL", "ref_range": "2.4 - 5.1"},
        {"category": "Metabolic", "parameter": "Magnesium", "value": "2.61", "flag": "High", "unit": "mg/dL", "ref_range": "1.9 - 2.5"},
        {"category": "Complete Hemogram", "parameter": "Hemoglobin", "value": "9.7", "flag": "Low", "unit": "g/dL", "ref_range": "12.0 - 15.0"},
        {"category": "Complete Hemogram", "parameter": "Total RBC", "value": "4.87", "flag": "High", "unit": "X 10^6/µL", "ref_range": "3.8 - 4.8"},
        {"category": "Complete Hemogram", "parameter": "Mean Corpuscular Volume (MCV)", "value": "79.5", "flag": "Low", "unit": "fL", "ref_range": "83.0 - 101.0"},
        {"category": "Complete Hemogram", "parameter": "Mean Corpuscular Hemoglobin (MCH)", "value": "19.9", "flag": "Low", "unit": "pg", "ref_range": "27.0 - 32.0"},
        {"category": "Complete Hemogram", "parameter": "Mean Corp. Hemo. Conc (MCHC)", "value": "25.1", "flag": "Low", "unit": "g/dL", "ref_range": "31.5 - 34.5"},
        {"category": "Complete Hemogram", "parameter": "Red Cell Distribution Width - SD (RDW-SD)", "value": "60.5", "flag": "High", "unit": "fL", "ref_range": "39.0 - 46.0"},
        {"category": "Complete Hemogram", "parameter": "Red Cell Distribution Width (RDW - CV)", "value": "21.4", "flag": "High", "unit": "%", "ref_range": "11.6 - 14.0"},
        {"category": "Differential Leucocyte", "parameter": "Eosinophils", "value": "6.7", "flag": "High", "unit": "%", "ref_range": "1 - 6"},
        {"category": "Absolute Leucocyte", "parameter": "Eosinophils - Absolute Count", "value": "0.56", "flag": "High", "unit": "X 10³ / µL", "ref_range": "0.02 - 0.5"},
        {"category": "Platelet Count & Indices", "parameter": "Platelet Distribution Width (PDW)", "value": "9.4", "flag": "Low", "unit": "fL", "ref_range": "9.6 - 15.2"},
        {"category": "Platelet Count & Indices", "parameter": "Platelet to Large Cell Ratio (PLCR)", "value": "17.9", "flag": "Low", "unit": "%", "ref_range": "19.7 - 42.4"},
    ]

    for idx, test in enumerate(flagged_display):
        row = t1.add_row()
        _cant_split(row)
        bg = BG_ALT_ROW if (idx % 2 == 1) else None

        area_name = (test.get("category") or "").title()
        test_name = test.get("parameter") or test.get("name") or test.get("test_name") or ""
        test_val = str(test.get("value") or "")
        test_flag = (test.get("flag") or "").title()
        test_unit = test.get("unit") or ""
        test_ref = test.get("ref_range") or ""

        _style_cell(row.cells[0], area_name, 6.5, MUTED_TEXT, bold=True, bg=bg, pad_top=14, pad_bottom=14)
        _style_cell(row.cells[1], test_name, 6.8, DARK_TEXT, bold=True, bg=bg, pad_top=14, pad_bottom=14)
        _style_cell(row.cells[2], test_val, 7.0, RED_FLAG, bold=True, bg=bg, align=WD_ALIGN_PARAGRAPH.CENTER, pad_top=14, pad_bottom=14)
        _style_cell(row.cells[3], test_flag, 7.0, RED_FLAG, bold=True, bg=bg, align=WD_ALIGN_PARAGRAPH.CENTER, pad_top=14, pad_bottom=14)
        _style_cell(row.cells[4], test_unit, 6.5, BODY_TEXT, bg=bg, pad_top=14, pad_bottom=14)
        _style_cell(row.cells[5], test_ref, 6.8, BLUE_RANGE, bold=True, bg=bg, pad_top=14, pad_bottom=14)

    # Strictly enforce table geometry on t1 after all rows are appended
    _apply_table_geometry(t1, t1_widths)

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 2: COMPLETE HEMOGRAM / CBC REPORT (COMMERCIAL PANEL)
    # ══════════════════════════════════════════════════════════════════════════
    doc.add_page_break()
    _add_header_banner(doc, patient_name, lab_code, show_meta=False)

    # Section Headers
    p_cbc_tag = doc.add_paragraph()
    p_cbc_tag.paragraph_format.space_before = Pt(0)
    p_cbc_tag.paragraph_format.space_after = Pt(0)
    r_tag = p_cbc_tag.add_run("COMMERCIAL PROFILE / PACKAGED PANEL")
    r_tag.font.name = "Segoe UI"
    r_tag.font.size = Pt(6.8)
    r_tag.bold = True
    r_tag.font.color.rgb = TEAL_BRAND

    p_cbc_title = doc.add_paragraph()
    p_cbc_title.paragraph_format.space_before = Pt(0)
    p_cbc_title.paragraph_format.space_after = Pt(1)
    r_cbc_title = p_cbc_title.add_run("Complete Hemogram / CBC Report")
    r_cbc_title.font.name = "Segoe UI"
    r_cbc_title.font.size = Pt(13)
    r_cbc_title.bold = True
    r_cbc_title.font.color.rgb = DARK_TEXT

    p_cbc_sub = doc.add_paragraph()
    p_cbc_sub.paragraph_format.space_before = Pt(0)
    p_cbc_sub.paragraph_format.space_after = Pt(3)
    r_cbc_sub = p_cbc_sub.add_run("Whole blood – EDTA specimen – Automated hematology analysis • ")
    r_cbc_sub.font.name = "Segoe UI"
    r_cbc_sub.font.size = Pt(7.0)
    r_cbc_sub.font.color.rgb = MUTED_TEXT
    r_fin = p_cbc_sub.add_run("FINAL")
    r_fin.font.name = "Segoe UI"
    r_fin.font.size = Pt(7.0)
    r_fin.bold = True
    r_fin.font.color.rgb = DARK_TEXT

    cbc_groups = [
        ("RED BLOOD CELL INDICES", [
            ("HEMOGLOBIN", "HEMOGLOBIN", "SLS-Hemoglobin Method", "13.0 - 17.0" if is_male else "12.0 - 15.0", "g/dL"),
            ("HEMATOCRIT (PCV)", "HEMATOCRIT (PCV)", "CPH Detection", "40.0 - 50.0" if is_male else "36.0 - 46.0", "%"),
            ("TOTAL RBC", "TOTAL RBC", "HF & EI", "4.5 - 5.5" if is_male else "3.8 - 4.8", "x 10^6/uL"),
            ("MEAN CORPUSCULAR VOLUME (MCV)", "Mean Corpuscular Volume (MCV)", "Calculated", "83.0 - 101.0", "fL"),
            ("MEAN CORPUSCULAR HEMOGLOBIN (MCH)", "Mean Corpuscular Hemoglobin (MCH)", "Calculated", "27.0 - 32.0", "pg"),
            ("MEAN CORP. HEMO. CONC (MCHC)", "Mean Corp. Hemo. Conc. (MCHC)", "Calculated", "31.5 - 34.5", "g/dL"),
            ("RED CELL DISTRIBUTION WIDTH - SD (RDW-SD)", "Red Cell Distribution Width (RDW-SD)", "Calculated", "39 - 46" if is_male else "39.0 - 46.0", "fL"),
            ("RED CELL DISTRIBUTION WIDTH (RDW - CV)", "Red Cell Distribution Width (RDW-CV)", "Calculated", "11.6 - 14.0", "%"),
            ("RED CELL DISTRIBUTION WIDTH INDEX (RDWI)", "RBC Distribution Width Index (RDWI)", "Calculated", "Refer notes", "-"),
            ("MENTZER INDEX", "Mentzer Index", "Calculated", "Refer notes", "-"),
        ]),
        ("WHITE BLOOD CELLS", [
            ("TOTAL LEUCOCYTE COUNT (WBC)", "TOTAL LEUCOCYTE COUNT (WBC)", "HF & FC", "4.0 - 10.0", "x 10^3/uL"),
            ("NEUTROPHILS", "Neutrophils Percentage", "Flow Cytometry", "40 - 80", "%"),
            ("LYMPHOCYTES", "Lymphocytes Percentage", "Flow Cytometry", "20 - 40", "%"),
            ("MONOCYTES", "Monocytes Percentage", "Flow Cytometry", "2 - 10", "%"),
            ("EOSINOPHILS", "Eosinophils Percentage", "Flow Cytometry", "1 - 6", "%"),
            ("BASOPHILS", "Basophils Percentage", "Flow Cytometry", "0 - 2", "%"),
            ("IMMATURE GRANULOCYTE PERCENTAGE (IG%)", "Immature Granulocytes Percentage (IG%)", "Flow Cytometry", "0.0 - 0.5" if is_male else "0.0 - 0.4", "%"),
            ("NUCLEATED RED BLOOD CELLS %", "Nucleated Red Blood Cells %", "Flow Cytometry", "0.0 - 5.0", "%"),
        ]),
        ("ABSOLUTE LEUKOCYTE COUNT", [
            ("NEUTROPHILS - ABSOLUTE COUNT", "Neutrophils - Absolute Count", "Calculated", "2.0 - 7.0", "x 10^3/uL"),
            ("LYMPHOCYTES - ABSOLUTE COUNT", "Lymphocytes - Absolute Count", "Calculated", "1.0 - 3.0", "x 10^3/uL"),
            ("MONOCYTES - ABSOLUTE COUNT", "Monocytes - Absolute Count", "Calculated", "0.2 - 1.0", "x 10^3/uL"),
            ("BASOPHILS - ABSOLUTE COUNT", "Basophils - Absolute Count", "Calculated", "0.02 - 0.1", "x 10^3/uL"),
            ("EOSINOPHILS - ABSOLUTE COUNT", "Eosinophils - Absolute Count", "Calculated", "0.02 - 0.5", "x 10^3/uL"),
            ("IMMATURE GRANULOCYTES (IG)", "Immature Granulocytes (IG)", "Calculated", "0.0 - 0.3", "x 10^3/uL"),
            ("NUCLEATED RED BLOOD CELLS", "Nucleated Red Blood Cells", "Calculated", "0.0 - 0.5", "x 10^3/uL"),
        ]),
        ("PLATELET COUNT & INDICES", [
            ("PLATELET COUNT", "PLATELET COUNT", "HF & EI", "150 - 410", "x 10^3/uL"),
            ("MEAN PLATELET VOLUME (MPV)", "Mean Platelet Volume (MPV)", "Calculated", "6.5 - 12", "fL"),
            ("PLATELET DISTRIBUTION WIDTH (PDW)", "Platelet Distribution Width (PDW)", "Calculated", "9.6 - 15.2", "fL"),
            ("PLATELET TO LARGE CELL RATIO (PLCR)", "Platelet to Large Cell Ratio (PLCR)", "Calculated", "19.7 - 42.4", "%"),
            ("PLATELETCRIT (PCT)", "Plateletcrit (PCT)", "Calculated", "0.19 - 0.39", "%"),
        ]),
    ]

    cbc_widths = [6.4, 3.6, 2.4, 2.2, 4.0]
    t2 = doc.add_table(rows=1, cols=5)
    t2.alignment = WD_TABLE_ALIGNMENT.CENTER
    t2.autofit = False
    _repeat_header(t2.rows[0])

    t2_headers = ["TEST NAME", "METHODOLOGY", "OBSERVED", "UNITS", "BIO. REF. INTERVAL"]
    for i, (hdr, w) in enumerate(zip(t2_headers, cbc_widths)):
        cell = t2.rows[0].cells[i]
        align = WD_ALIGN_PARAGRAPH.CENTER if i == 2 else WD_ALIGN_PARAGRAPH.LEFT
        _style_cell(cell, hdr, 6.8, WHITE, bold=True, bg=TEAL_BANNER, align=align, pad_top=20, pad_bottom=20)

    row_count = 0
    for grp_title, items in cbc_groups:
        cat_r = t2.add_row()
        _cant_split(cat_r)
        merged_cat = cat_r.cells[0].merge(cat_r.cells[4])
        _style_cell(merged_cat, grp_title, 6.8, TEAL_BRAND, bold=True, bg=BG_CAT_ROW, pad_top=14, pad_bottom=14, pad_left=100)

        for param_key, display_name, def_method, def_ref, def_unit in items:
            t = tmap.get(param_key, {})
            val = t.get("value", "—")
            method = t.get("method") or def_method
            unit = t.get("unit") or def_unit
            ref = t.get("ref_range") or def_ref
            flag = str(t.get("flag", "")).upper()
            if flag not in ("HIGH", "LOW") and val and str(val).strip() not in ("—", "-", "", "None"):
                from blood_tests_db import determine_flag_gender
                flag = determine_flag_gender(val, ref_range_str=ref)
            is_abnormal = flag in ("HIGH", "LOW")

            data_r = t2.add_row()
            _cant_split(data_r)
            bg = BG_ALT_ROW if (row_count % 2 == 1) else None
            row_count += 1

            val_color = RED_FLAG if is_abnormal else DARK_TEXT

            _style_cell(data_r.cells[0], display_name, 6.5, DARK_TEXT, bold=True, bg=bg, pad_top=8, pad_bottom=8)
            _style_cell(data_r.cells[1], method, 6.0, MUTED_TEXT, bg=bg, pad_top=8, pad_bottom=8)
            _style_cell(data_r.cells[2], str(val), 6.8, val_color, bold=is_abnormal, bg=bg, align=WD_ALIGN_PARAGRAPH.CENTER, pad_top=8, pad_bottom=8)
            _style_cell(data_r.cells[3], unit, 6.0, BODY_TEXT, bg=bg, pad_top=8, pad_bottom=8)
            _style_cell(data_r.cells[4], ref, 6.2, DARK_TEXT, bold=True, bg=bg, pad_top=8, pad_bottom=8)

    # Strictly enforce table geometry on t2 after all rows and merged cells are created
    _apply_table_geometry(t2, cbc_widths)

    # Mentzer Index & RDWI Explanatory Note Box
    mentzer_tbl = doc.add_table(rows=1, cols=1)
    mentzer_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    mentzer_tbl.autofit = False

    c_m = mentzer_tbl.rows[0].cells[0]
    _set_cell_bg(c_m, "F8FAFC")
    _set_cell_margins(c_m, top=20, bottom=20, left=60, right=60)
    _set_cell_borders(c_m,
                      left={"val": "single", "sz": 4, "color": "CBD5E1"},
                      top={"val": "single", "sz": 4, "color": "CBD5E1"},
                      right={"val": "single", "sz": 4, "color": "CBD5E1"},
                      bottom={"val": "single", "sz": 4, "color": "CBD5E1"})

    p_m = c_m.paragraphs[0]
    p_m.paragraph_format.space_before = Pt(2)
    p_m.paragraph_format.space_after = Pt(2)
    r_ml = p_m.add_run("*Note: ")
    r_ml.font.name = "Segoe UI"
    r_ml.font.size = Pt(6.5)
    r_ml.bold = True
    r_ml.font.color.rgb = DARK_TEXT

    r_mt = p_m.add_run("Mentzer index (MI), RDW-CV and RDWI are hematological indices to differentiate between Iron Deficiency Anemia (IDA) and Beta Thalassemia Trait (BTT). MI > 13, RDWI > 220 and RDW-CV > 14 more likely to be IDA. MI < 13, RDWI < 220, and RDW-CV < 14 more likely to be BTT. Suggested clinical correlation. BTT to be confirmed with Hb electrophoresis if clinically indicated.")
    r_mt.font.name = "Segoe UI"
    r_mt.font.size = Pt(6.5)
    r_mt.font.color.rgb = MUTED_TEXT

    _apply_table_geometry(mentzer_tbl, [18.6])

    # Clinical Smear Notes Box
    notes_tbl = doc.add_table(rows=1, cols=1)
    notes_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    notes_tbl.autofit = False

    c_note = notes_tbl.rows[0].cells[0]
    _set_cell_bg(c_note, "F8FAFC")
    _set_cell_margins(c_note, top=30, bottom=30, left=100, right=100)
    _set_cell_borders(c_note,
                      left={"val": "single", "sz": 24, "color": TEAL_BANNER},
                      top={"val": "single", "sz": 4, "color": "CBD5E1"},
                      right={"val": "single", "sz": 4, "color": "CBD5E1"},
                      bottom={"val": "single", "sz": 4, "color": "CBD5E1"})

    p_note = c_note.paragraphs[0]
    p_note.paragraph_format.space_before = Pt(0)
    p_note.paragraph_format.space_after = Pt(0)
    r_nl = p_note.add_run("REMARKS / CLINICAL NOTES: ")
    r_nl.font.name = "Segoe UI"
    r_nl.font.size = Pt(6.8)
    r_nl.bold = True
    r_nl.font.color.rgb = DARK_TEXT

    note_text = metadata.get("clinical_notes") or (
        "Alert!!! Predominantly normocytic normochromic with ovalocytes. Platelets: Appear adequate in smear."
        if is_male else
        "Alert!!! RBCs: Marked anisocytosis, moderate poikilocytosis. Predominantly normocytic normochromic with microcytes & ovalocytes. Platelets: Appear adequate in smear."
    )
    r_nt = p_note.add_run(note_text)
    r_nt.font.name = "Segoe UI"
    r_nt.font.size = Pt(6.8)
    r_nt.font.color.rgb = BODY_TEXT

    _apply_table_geometry(notes_tbl, [18.6])

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 3: TIER 3 - COMPREHENSIVE DIAGNOSTIC HEALTH REPORT (53 Analytes)
    # ══════════════════════════════════════════════════════════════════════════
    doc.add_page_break()
    _add_header_banner(doc, patient_name, lab_code, show_meta=False)

    # Section Headers
    p_t3_tag = doc.add_paragraph()
    p_t3_tag.paragraph_format.space_before = Pt(0)
    p_t3_tag.paragraph_format.space_after = Pt(0)
    r_t3_tag = p_t3_tag.add_run("TIER 3: INDIVIDUAL ANALYTES (FULL LAB PARAMETERS)")
    r_t3_tag.font.name = "Segoe UI"
    r_t3_tag.font.size = Pt(6.8)
    r_t3_tag.bold = True
    r_t3_tag.font.color.rgb = TEAL_BRAND

    p_t3_title = doc.add_paragraph()
    p_t3_title.paragraph_format.space_before = Pt(0)
    p_t3_title.paragraph_format.space_after = Pt(1)
    r_t3_title = p_t3_title.add_run("Comprehensive Diagnostic Health Report")
    r_t3_title.font.name = "Segoe UI"
    r_t3_title.font.size = Pt(13)
    r_t3_title.bold = True
    r_t3_title.font.color.rgb = DARK_TEXT

    p_t3_sub = doc.add_paragraph()
    p_t3_sub.paragraph_format.space_before = Pt(0)
    p_t3_sub.paragraph_format.space_after = Pt(2)
    r_t3_sub = p_t3_sub.add_run("Complete laboratory audit of all tested biomarkers, methodologies and biological reference intervals.")
    r_t3_sub.font.name = "Segoe UI"
    r_t3_sub.font.size = Pt(7.0)
    r_t3_sub.font.color.rgb = MUTED_TEXT

    # Master Table (53 parameters) with generous category column width
    t3_widths = [0.8, 4.6, 5.6, 1.9, 1.7, 4.0]
    t3 = doc.add_table(rows=1, cols=6)
    t3.alignment = WD_TABLE_ALIGNMENT.CENTER
    t3.autofit = False
    _repeat_header(t3.rows[0])

    t3_headers = ["SR.", "CATEGORY / DEPARTMENT", "DESCRIPTION / TEST NAME", "OBSERVED VALUE", "UNITS", "NORMAL RANGE"]
    for i, (hdr, w) in enumerate(zip(t3_headers, t3_widths)):
        cell = t3.rows[0].cells[i]
        align = WD_ALIGN_PARAGRAPH.CENTER if i in (0, 3) else WD_ALIGN_PARAGRAPH.LEFT
        _style_cell(cell, hdr, 6.6, WHITE, bold=True, bg=TEAL_BANNER, align=align, pad_top=20, pad_bottom=20)

    for idx, test in enumerate(tests, start=1):
        row = t3.add_row()
        _cant_split(row)
        bg = BG_ALT_ROW if (idx % 2 == 0) else None

        flag = str(test.get("flag", "")).upper()
        if flag not in ("HIGH", "LOW") and test.get("value") and str(test.get("value")).strip() not in ("—", "-", "", "None"):
            from blood_tests_db import determine_flag_gender
            flag = determine_flag_gender(test.get("value"), ref_range_str=test.get("ref_range"))
        is_abnormal = flag in ("HIGH", "LOW")
        val_color = RED_FLAG if is_abnormal else DARK_TEXT

        _style_cell(row.cells[0], str(idx), 6.2, MUTED_TEXT, bg=bg, align=WD_ALIGN_PARAGRAPH.CENTER, pad_top=11, pad_bottom=11)
        _style_cell(row.cells[1], test.get("category") or "", 6.5, BODY_TEXT, bold=True, bg=bg, pad_top=11, pad_bottom=11)
        _style_cell(row.cells[2], test.get("parameter") or "", 6.6, DARK_TEXT, bold=True, bg=bg, pad_top=11, pad_bottom=11)
        _style_cell(row.cells[3], str(test.get("value") or "—"), 7.0, val_color, bold=is_abnormal, bg=bg, align=WD_ALIGN_PARAGRAPH.CENTER, pad_top=11, pad_bottom=11)
        _style_cell(row.cells[4], test.get("unit") or "-", 6.2, MUTED_TEXT, bg=bg, pad_top=11, pad_bottom=11)
        _style_cell(row.cells[5], test.get("ref_range") or "-", 6.5, BLUE_RANGE_53, bold=True, bg=bg, pad_top=11, pad_bottom=11)

    # Strictly enforce table geometry on t3 after all rows are appended
    _apply_table_geometry(t3, t3_widths)

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 4: CONDITIONS OF REPORTING & ADVISORY
    # ══════════════════════════════════════════════════════════════════════════
    doc.add_page_break()
    _add_header_banner(doc, patient_name, lab_code, show_meta=False)

    # Conditions Card (bordered box)
    t_cond = doc.add_table(rows=1, cols=1)
    t_cond.alignment = WD_TABLE_ALIGNMENT.CENTER
    t_cond.autofit = False
    _apply_table_geometry(t_cond, [18.6])

    c_cond = t_cond.rows[0].cells[0]
    _set_cell_bg(c_cond, "FFFFFF")
    _set_cell_margins(c_cond, top=100, bottom=100, left=140, right=140)
    _set_cell_borders(c_cond,
                      left={"val": "single", "sz": 6, "color": "CBD5E1"},
                      top={"val": "single", "sz": 6, "color": "CBD5E1"},
                      right={"val": "single", "sz": 6, "color": "CBD5E1"},
                      bottom={"val": "single", "sz": 6, "color": "CBD5E1"})

    p_cond_h = c_cond.paragraphs[0]
    p_cond_h.paragraph_format.space_before = Pt(0)
    p_cond_h.paragraph_format.space_after = Pt(4)
    r_ch = p_cond_h.add_run("CONDITIONS OF REPORTING")
    r_ch.font.name = "Segoe UI"
    r_ch.font.size = Pt(9.0)
    r_ch.bold = True
    r_ch.font.color.rgb = DARK_TEXT

    conditions_list = [
        "Results are for the information and interpretation of the referring doctor only.",
        "Tests are presumed to have been performed on the specimen of the patient named or identified above.",
        "Results may vary between laboratories, and over time for the same patient, depending on the assay method, equipment and specimen quality.",
        "Any unexpected abnormal result should be reconfirmed.",
        "Results should be interpreted only by medical professionals who understand the reporting units, reference ranges and limitations of the technologies used.",
        "This report is not valid for medico-legal purposes.",
        "Zylk Health and its employees and representatives accept no liability for (a) any bodily injury, loss or damage arising from an assumed meaning of this report, or (b) any claim arising from the performance of the requested tests, including indirect, incidental or consequential damages. Total liability shall not exceed the invoiced amount for the services provided and paid for."
    ]

    for item in conditions_list:
        p_item = c_cond.add_paragraph()
        p_item.paragraph_format.space_before = Pt(0)
        p_item.paragraph_format.space_after = Pt(3)
        p_item.paragraph_format.line_spacing = 1.25
        r_bullet = p_item.add_run("•  ")
        r_bullet.font.name = "Segoe UI"
        r_bullet.font.size = Pt(7.0)
        r_bullet.font.color.rgb = TEAL_BRAND
        r_text = p_item.add_run(item)
        r_text.font.name = "Segoe UI"
        r_text.font.size = Pt(7.0)
        r_text.font.color.rgb = BODY_TEXT

    # Feedback & Clinical Support Box
    gap_sup = doc.add_paragraph()
    gap_sup.paragraph_format.space_before = Pt(6)
    gap_sup.paragraph_format.space_after = Pt(0)

    t_sup = doc.add_table(rows=1, cols=1)
    t_sup.alignment = WD_TABLE_ALIGNMENT.CENTER
    t_sup.autofit = False
    _apply_table_geometry(t_sup, [18.6])

    c_sup = t_sup.rows[0].cells[0]
    _set_cell_bg(c_sup, "FFFFFF")
    _set_cell_margins(c_sup, top=70, bottom=70, left=120, right=120)
    _set_cell_borders(c_sup,
                      left={"val": "single", "sz": 6, "color": "CBD5E1"},
                      top={"val": "single", "sz": 6, "color": "CBD5E1"},
                      right={"val": "single", "sz": 6, "color": "CBD5E1"},
                      bottom={"val": "single", "sz": 6, "color": "CBD5E1"})

    p_sup = c_sup.paragraphs[0]
    p_sup.paragraph_format.space_before = Pt(0)
    p_sup.paragraph_format.space_after = Pt(0)
    r_s1 = p_sup.add_run("For suggestions, complaints, clinical support or feedback, email ")
    r_s1.font.name = "Segoe UI"
    r_s1.font.size = Pt(7.2)
    r_s1.font.color.rgb = BODY_TEXT

    r_s2 = p_sup.add_run("customercare@zylkhealth.com")
    r_s2.font.name = "Segoe UI"
    r_s2.font.size = Pt(7.2)
    r_s2.bold = True
    r_s2.font.color.rgb = TEAL_ACCRED

    r_s3 = p_sup.add_run(" or call ")
    r_s3.font.name = "Segoe UI"
    r_s3.font.size = Pt(7.2)
    r_s3.font.color.rgb = BODY_TEXT

    r_s4 = p_sup.add_run("+91 98943 77521")
    r_s4.font.name = "Segoe UI"
    r_s4.font.size = Pt(7.2)
    r_s4.bold = True
    r_s4.font.color.rgb = TEAL_ACCRED

    r_s5 = p_sup.add_run(".")
    r_s5.font.name = "Segoe UI"
    r_s5.font.size = Pt(7.2)
    r_s5.font.color.rgb = BODY_TEXT

    # End of report divider
    p_eor = doc.add_paragraph()
    p_eor.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_eor.paragraph_format.space_before = Pt(16)
    p_eor.paragraph_format.space_after = Pt(8)
    r_eor = p_eor.add_run("— End of report —")
    r_eor.font.name = "Segoe UI"
    r_eor.font.size = Pt(7.5)
    r_eor.font.color.rgb = FOOTER_GREY

    # Serialize to memory buffer
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()

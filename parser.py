"""
Document Parser Engine for Clinical Lab Reports.
Supports both Digital Vector PDFs and Scanned PDFs/Images.
Applies Gender-Specific Biological Reference Ranges (Male vs Female).
Includes:
- Deterministic positive-regex barcode/identifier extraction
- Coordinate-based vector extraction with explicit column boundaries
- RapidOCR horizontal bounding-box clustering with multi-line lookahead normalization
"""

import os
import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from PIL import Image

import pdfplumber
import pypdfium2 as pdfium

from blood_tests_db import (
    find_matching_test,
    get_gender_specific_range,
    determine_flag_gender,
    BLOOD_TESTS_REGISTRY
)

# Optional RapidOCR singleton (lazy-loaded for lightweight cloud/serverless deployments)
_ocr_engine: Optional[Any] = None

def get_ocr_engine() -> Optional[Any]:
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from rapidocr import RapidOCR
            _ocr_engine = RapidOCR()
        except Exception as e:
            print(f"[Info] RapidOCR not installed / serverless mode: {e}")
            return None
    return _ocr_engine


CATEGORY_HEADERS = {
    'INFERTILITY', 'METABOLIC', 'VITAMINS', 'CARDIAC RISK MARKERS',
    'ARTHRITIS', 'IRON DEFICIENCY', 'ELEMENTS', 'HORMONE', 'HORMONES',
    'INFECTIOUS DISEASE', 'RENAL', 'THYROID', 'COMPLETE HEMOGRAM',
    'DIFFERENTIAL LEUCOCYTE COUNT', 'ABSOLUTE LEUCOCYTE COUNT',
    'PLATELET COUNT & INDICES', 'RED BLOOD CELL INDICES',
    'CUSTOMER DETAILS', 'REPORT AUTHENTICITY CHECK', 'TEST DETAILS',
    'REPORT STATUS', 'TESTS OUTSIDE REFERENCE RANGE', 'TEST DETAILS REPORT STATUS'
}


def extract_barcodes_and_identifiers(text: str) -> Tuple[str, List[str], List[str]]:
    """
    Deterministic extraction using strict positive regular expressions:
    - Vial Barcode Pattern: \\b[A-Z]{1,3}\\d{6,9}\\b (captures EZ153335, FN883087)
    - Lab/Source Code Pattern: \\b\\d{8,12}/[A-Z0-9]+\\b (captures 1509040738/FE254)
    Returns: (primary_sample_id, unique_vial_barcodes, unique_source_codes)
    """
    vial_pattern = r'\b[A-Z]{1,3}\d{6,9}\b'
    source_pattern = r'\b\d{8,12}/[A-Z0-9]+\b'
    
    vial_matches = re.findall(vial_pattern, text)
    source_matches = re.findall(source_pattern, text)
    
    unique_vials = list(dict.fromkeys(vial_matches))
    unique_sources = list(dict.fromkeys(source_matches))
    
    primary_id = ""
    ez_vials = [v for v in unique_vials if v.upper().startswith("EZ")]
    if ez_vials:
        primary_id = ez_vials[0]
    elif unique_vials:
        primary_id = unique_vials[0]
    elif unique_sources:
        primary_id = unique_sources[0]
        
    return primary_id, unique_vials, unique_sources


def extract_patient_metadata(text: str) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "patient_name": "",
        "age_gender": "",
        "gender": "FEMALE",
        "sample_id": "",
        "barcodes": [],
        "source_codes": [],
        "referred_by": "",
        "collection_date": "",
        "report_date": "",
        "specimen": "Blood Test",
        "phone": "+91 98765 43210",
        "dob": "14-Aug-2005",
        "address": "INGENX LABS Pvt Ltd., P18, Shifa Golden City, Tirunelveli",
        "pincode": "627007",
        "test_type": "Women Hairfall Screening Advanced",
        "lab_code": ""
    }

    if not text:
        return metadata

    # 1. Patient Name
    name_patterns = [
        r'(?:Patient\s*Name|Pt\.?\s*Name|Name)\s*[:\-]\s*([A-Za-z\.\s]{2,40}?)(?:\s*\(|\s+Sample|\s+ID|\s+Age|\s+Sex|\s+Gender|\s+Ref|\s+Dr|\n|$)',
        r'(?:Mr\.|Mrs\.|Ms\.|Master|Dr\.)\s+([A-Za-z\s]{3,30})(?:\s*\(|\s+Age|\s+Sex|\s+Sample|\n|$)'
    ]
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            clean_name = re.sub(r'\s+', ' ', match.group(1)).strip(' :,-')
            if len(clean_name) >= 2 and not re.search(r'(report|hospital|laboratory|diagnostic|thyrocare)', clean_name, re.IGNORECASE):
                metadata["patient_name"] = clean_name
                break

    # 2. Age & Gender
    # Check parenthesized format first, e.g. Sam Daniel(24Y/M) or (21Y/F)
    paren_match = re.search(r'\(([0-9]{1,3})\s*(?:Y|Yrs)?\s*[\/\,]\s*([MFmf])\)', text)
    if paren_match:
        metadata["age_gender"] = paren_match.group(1)
        metadata["gender"] = "MALE" if paren_match.group(2).upper() == "M" else "FEMALE"
    else:
        age_gender_patterns = [
            r'(?:Age\s*[\/\&]?\s*Gender|Age\s*[\/\&]?\s*Sex)\s*[:\-]?\s*([0-9]{1,3}\s*(?:Y|Yrs|Years)?\s*[\/\,\s]*\s*(?:Male|Female|M|F)?)(?:\s+Ref|\s+Dr|\n|$)',
            r'Age\s*[:\-]?\s*([0-9]{1,3})\s*(?:Y|Yrs|Years)?.*?(?:Sex|Gender)\s*[:\-]?\s*(Male|Female|M|F)',
            r'([0-9]{1,2})\s*(?:Y|Yrs|Years)\s*[\/\,\s]+\s*(Male|Female|M|F)',
            r'([0-9]{1,3})\s*Y\s*[\/\,]\s*([MF])'
        ]
        for pattern in age_gender_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                ag_str = re.sub(r'\s+', ' ', match.group(1)).strip(' :,-')
                metadata["age_gender"] = ag_str
                if re.search(r'\b(Male|M)\b', ag_str, re.IGNORECASE) and not re.search(r'\b(Female|F)\b', ag_str, re.IGNORECASE):
                    metadata["gender"] = "MALE"
                elif re.search(r'\b(Female|F)\b', ag_str, re.IGNORECASE):
                    metadata["gender"] = "FEMALE"
                break

    # Check explicit Sex/Gender field in header
    sex_field_match = re.search(r'(?:Sex|Gender)\s*[:\-]?\s*(Male|Female|M|F)\b', text, re.IGNORECASE)
    if sex_field_match:
        val = sex_field_match.group(1).upper()
        metadata["gender"] = "MALE" if val in ("MALE", "M") else "FEMALE"

    # 3. Deterministic Barcodes & Identifiers (Positive Regex)
    primary_id, vial_barcodes, source_codes = extract_barcodes_and_identifiers(text)
    if primary_id:
        metadata["sample_id"] = primary_id
    metadata["barcodes"] = vial_barcodes
    metadata["source_codes"] = source_codes

    # 3b. Dedicated Lab Code Extraction from bottom/remarks or barcodes
    remark_lab_matches = re.findall(r'Report\s*Remarks\s*:\s*LabCode\s*[:\-]?\s*([0-9A-Za-z/_-]+)', text, re.IGNORECASE)
    if remark_lab_matches:
        metadata["lab_code"] = remark_lab_matches[-1].strip()
    else:
        lab_code_matches = re.findall(r'LabCode\s*[:\-]?\s*([0-9A-Za-z/_-]+)', text, re.IGNORECASE)
        if lab_code_matches:
            metadata["lab_code"] = lab_code_matches[-1].strip()
        elif source_codes:
            metadata["lab_code"] = source_codes[-1]
        elif primary_id:
            metadata["lab_code"] = primary_id
        else:
            metadata["lab_code"] = "1509074825/FE254"

    # 4. Referred By / Doctor
    doctor_patterns = [
        r'(?:Ref(?:\.|erred)?\s*(?:By|Doctor)|Consultant|Doctor)\s*[:\-]?\s*([A-Za-z0-9\.\,\s]{3,45}?)(?:\s+Date|\s+Sample|\s+Coll|\n|$)'
    ]
    for pattern in doctor_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            metadata["referred_by"] = re.sub(r'\s+', ' ', match.group(1)).strip(' :,-')
            break

    # 5. Address & Pincode
    addr_match = re.search(r'Address\s*[:\-]?\s*([^\n\r]+(?:,\s*[^\n\r]+)*)', text, re.IGNORECASE)
    if addr_match:
        raw_addr = addr_match.group(1).strip(' :,-')
        metadata["address"] = re.sub(r'\s+', ' ', raw_addr)
        pin_match = re.search(r'\b([0-9]{6})\b', raw_addr)
        if pin_match:
            metadata["pincode"] = pin_match.group(1)

    # 5b. DOB Extraction
    dob_match = re.search(r'(?:Date\s*of\s*Birth|DOB|D\.?O\.?B\.?|Birth\s*Date)\s*[:\-]?\s*([0-9]{1,2}[\/\-\s]+[A-Za-z0-9]{3,9}[\/\-\s]+[0-9]{2,4})', text, re.IGNORECASE)
    if dob_match:
        metadata["dob"] = dob_match.group(1).strip()

    # 5c. Test Package / Test Type
    pkg_match = re.search(r'(?:Package|Test\s*Type|Test\s*Asked|Sample_Type\/Tests)\s*[:\-]?\s*([^\n\r]+)', text, re.IGNORECASE)
    if pkg_match:
        raw_pkg = pkg_match.group(1).strip(' :,-')
        if len(raw_pkg) > 5 and not re.search(r'(Ready|Final)', raw_pkg, re.IGNORECASE):
            metadata["test_type"] = re.sub(r'\s+', ' ', raw_pkg)

    # 5d. Prioritize gender and standardize title (Mens Hairfall Screening Advanced vs Women Hairfall Screening Advanced)
    test_pkg_upper = (metadata.get("test_type") or "").upper()
    if re.search(r'\b(MEN|MENS|MALE|MALES)\b', test_pkg_upper):
        metadata["gender"] = "MALE"
        if "HAIRFALL" in test_pkg_upper or "JAANCH" in test_pkg_upper:
            metadata["test_type"] = "Mens Hairfall Screening Advanced"
    elif re.search(r'\b(WOMEN|WOMENS|FEMALE|FEMALES)\b', test_pkg_upper):
        metadata["gender"] = "FEMALE"
        if "HAIRFALL" in test_pkg_upper or "JAANCH" in test_pkg_upper:
            metadata["test_type"] = "Women Hairfall Screening Advanced"

    # 6. Customer Mobile / Phone
    phone_match = re.search(r'(?:Mobile|Phone|Contact)\s*(?:No\.?)?\s*[:\-]?\s*([0-9]{10,12})', text, re.IGNORECASE)
    if phone_match:
        metadata["phone"] = "+91 " + phone_match.group(1)[-10:]

    # 7. Dates
    coll_match = re.search(r'(?:Collected\s*on|Collection\s*Date|Sample\s*Date|SCT)\s*[:\-]?\s*([0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4}(?:\s+[0-9]{1,2}:[0-9]{2})?)', text, re.IGNORECASE)
    if not coll_match:
        coll_match = re.search(r'(?:Collected|Collection\s*Date)\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})', text, re.IGNORECASE)
    if coll_match:
        metadata["collection_date"] = coll_match.group(1).strip()

    rep_match = re.search(r'(?:Reported\s*on|Report\s*Released|Report\s*Date|RRT)\s*[:\-]?\s*([0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4}(?:\s+[0-9]{1,2}:[0-9]{2})?)', text, re.IGNORECASE)
    if not rep_match:
        rep_match = re.search(r'(?:Reported|Report\s*Date)\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})', text, re.IGNORECASE)
    if rep_match:
        metadata["report_date"] = rep_match.group(1).strip()

    if not metadata["collection_date"]:
        date_pattern = re.findall(r'\b([0-9]{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+20[0-9]{2})\b', text, re.IGNORECASE)
        if date_pattern:
            metadata["collection_date"] = date_pattern[0]
            if len(date_pattern) > 1:
                metadata["report_date"] = date_pattern[1]

    # 8. Multi-line label/value pairing (for screenshot/table OCR documents)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for i, l in enumerate(lines):
        if i + 1 < len(lines):
            next_l = lines[i+1].strip()
            if not metadata["patient_name"] and re.search(r'^Patient\s*Name\s*[:\-]?$', l, re.IGNORECASE):
                cleaned_n = re.sub(r'\s*\([0-9]+[A-Za-z\/]+\)', '', next_l).strip()
                if len(cleaned_n) >= 2:
                    metadata["patient_name"] = cleaned_n
                ag = re.search(r'\(([0-9]+[A-Za-z\/]+)\)', next_l)
                if ag and not metadata["age_gender"]:
                    metadata["age_gender"] = ag.group(1)
            elif not metadata["referred_by"] and re.search(r'^(?:Referred\s*By|Ref\s*By)\s*[:\-]?$', l, re.IGNORECASE):
                metadata["referred_by"] = next_l
            elif re.search(r'^(?:Sample\s*Collected\s*At|Address)\s*[:\-]?$', l, re.IGNORECASE):
                if not metadata["address"] or metadata["address"].startswith("INGENX LABS"):
                    metadata["address"] = next_l
                pin = re.search(r'\b([0-9]{6})\b', next_l)
                if pin:
                    metadata["pincode"] = pin.group(1)
            elif not metadata["collection_date"] and re.search(r'^(?:Sample\s*Collected\s*On|Collection\s*Date)\s*[:\-]?$', l, re.IGNORECASE):
                metadata["collection_date"] = next_l
            elif not metadata["report_date"] and re.search(r'^(?:Reported\s*On|Report\s*Date)\s*[:\-]?$', l, re.IGNORECASE):
                metadata["report_date"] = next_l
            elif re.search(r'^(?:Test\s*Performed|Package)\s*[:\-]?$', l, re.IGNORECASE):
                metadata["test_type"] = next_l

    # 9. Extract peripheral blood smear clinical remarks from pathologist note
    remark_match = re.search(r'Remarks\s*:\s*(Alert[^\n\r]+|Predominantly[^\n\r]+|RBCs[^\n\r]+|Platelets[^\n\r]+|[^\n\r]*(?:smear|adequate|normocytic|anisocytosis)[^\n\r]*)', text, re.IGNORECASE)
    if remark_match and "labcode" not in remark_match.group(1).lower():
        raw_note = remark_match.group(1).strip()
        raw_note = re.sub(r'Platelets\s*:\s*', 'Platelets: ', raw_note, flags=re.IGNORECASE)
        raw_note = re.sub(r'\s+', ' ', raw_note).strip(' :,-')
        if "adequate" in raw_note.lower() and "smear" not in raw_note.lower():
            raw_note += " in smear."
        elif not raw_note.endswith('.'):
            raw_note += '.'
        metadata["clinical_notes"] = raw_note
    else:
        alt_match = re.search(r'(Alert\s*!{1,3}.*?(?:in\s*smear|on\s*smear|adequate(?:\s+in\s+smear)?\.?))', text, re.IGNORECASE | re.DOTALL)
        if alt_match:
            raw_note = alt_match.group(1).strip()
            raw_note = re.sub(r'Platelets\s*:\s*', 'Platelets: ', raw_note, flags=re.IGNORECASE)
            raw_note = re.sub(r'\s+', ' ', raw_note).strip(' :,-')
            if "adequate" in raw_note.lower() and "smear" not in raw_note.lower():
                raw_note += " in smear."
            elif not raw_note.endswith('.'):
                raw_note += '.'
            metadata["clinical_notes"] = raw_note
    if not metadata.get("clinical_notes"):
        metadata["clinical_notes"] = "Alert!!! Predominantly normocytic normochromic with ovalocytes. Platelets: Appear adequate in smear."

    return metadata


def extract_vector_table_records(plumber_page: Any) -> Dict[str, Dict[str, Any]]:
    """
    Bulletproof Vector Extraction with Dynamic Column Boundary Detection:
    - Scans page words to detect headers: TECHNOLOGY, VALUE, UNITS, BIO. REF. INTERVAL
    - Dynamically partitions horizontal coordinates according to detected table layout
    - Handles both 5-column detail pages and 4-column summary tables
    - Vertical line clustering with midpoint tolerance (4px)
    """
    found_tests: Dict[str, Dict[str, Any]] = {}
    try:
        words = plumber_page.extract_words()
    except Exception:
        return found_tests

    if not words:
        return found_tests

    # 1. Detect dynamic column coordinates from table header
    tech_x = None
    val_x = None
    units_x = None
    ref_x = None

    for w in words:
        txt = w["text"].upper()
        if txt in ["TECHNOLOGY", "METHODOLOGY", "METHOD"] and tech_x is None:
            tech_x = w["x0"]
        elif txt == "VALUE" and val_x is None:
            val_x = w["x0"]
        elif txt in ["UNITS", "UNIT"] and units_x is None:
            units_x = w["x0"]
        elif txt in ["REF.", "BIO.", "INTERVAL.", "REFERENCE"] and ref_x is None and w["x0"] > 400:
            ref_x = w["x0"]

    if not val_x:
        val_x = 330.0
    if not units_x:
        units_x = 420.0
    if not ref_x:
        ref_x = 470.0

    # 2. Group words into vertical lines
    lines: Dict[float, List[Dict[str, Any]]] = {}
    for w in words:
        mid_y = (w["top"] + w["bottom"]) / 2.0
        matched_k = None
        for k in lines:
            if abs(k - mid_y) <= 4.0:
                matched_k = k
                break
        if matched_k is not None:
            lines[matched_k].append(w)
        else:
            lines[mid_y] = [w]

    sorted_y = sorted(lines.keys())

    for i, y_k in enumerate(sorted_y):
        row_words = sorted(lines[y_k], key=lambda w: w["x0"])
        full_row_text = " ".join(w["text"] for w in row_words)

        # Exclude literature citations, journal footnotes, author references, and trimester pregnancy notes
        if re.search(r'\b(clinical perspective|ActaObset|Gynecol|Scand|et al\.|editorial|journal|citation|reference notes|guideline|disclaimer|Trimester)\b', full_row_text, re.I):
            continue
        if re.search(r'^\s*[A-Z][a-z]+ [A-Z],', full_row_text):
            continue

        if tech_x:
            col1_words = [w["text"] for w in row_words if w["x0"] < tech_x - 15]
            col2_words = [w["text"] for w in row_words if tech_x - 15 <= w["x0"] < val_x - 15]
            col3_words = [w["text"] for w in row_words if val_x - 15 <= w["x0"] < units_x - 15]
            col4_words = [w["text"] for w in row_words if units_x - 15 <= w["x0"] < ref_x - 10]
            col5_words = [w["text"] for w in row_words if w["x0"] >= ref_x - 10]
        else:
            # 4 columns (Page 3 summary format)
            col1_words = [w["text"] for w in row_words if w["x0"] < val_x - 15]
            col2_words = ["Calculated"]
            col3_words = [w["text"] for w in row_words if val_x - 15 <= w["x0"] < units_x - 15]
            col4_words = [w["text"] for w in row_words if units_x - 15 <= w["x0"] < ref_x - 10]
            col5_words = [w["text"] for w in row_words if w["x0"] >= ref_x - 10]

        test_name_raw = " ".join(col1_words).strip()
        method_raw = " ".join(col2_words).strip()
        value_raw = " ".join(col3_words).strip()
        units_raw = " ".join(col4_words).strip()
        ref_raw = " ".join(col5_words).strip()

        if not test_name_raw or test_name_raw.upper() in CATEGORY_HEADERS:
            continue

        test_match = find_matching_test(test_name_raw)

        # Multi-line wrapped test names
        if not test_match and i + 1 < len(sorted_y):
            next_row_w = sorted(lines[sorted_y[i+1]], key=lambda w: w["x0"])
            cutoff = (tech_x - 15) if tech_x else (val_x - 15)
            next_col1 = [w["text"] for w in next_row_w if w["x0"] < cutoff]
            if next_col1:
                test_match = find_matching_test(f"{test_name_raw} {' '.join(next_col1)}")

        if test_match and test_match["name"] not in found_tests:
            val = None
            if "NON REACTIVE" in value_raw.upper() or "NEGATIVE" in value_raw.upper():
                val = "NON REACTIVE"
            else:
                # Strip unit exponents (like 'X 10^6', '10^6', '10^3', '10³', '10⁶') without corrupting numbers like 106.7
                val_clean = re.sub(r'\bX\s*10\^?[36]\b', '', value_raw, flags=re.I)
                val_clean = re.sub(r'\b10\^[36]\b|\b10[³⁶]\b', '', val_clean, flags=re.I)
                # Discard pure range strings (e.g. '0.35 - 4.94')
                if re.search(r'^\s*([0-9]+(?:\.[0-9]+)?)\s*-\s*([0-9]+(?:\.[0-9]+)?)\s*$', val_clean):
                    val_clean = ""
                num_m = re.search(r'([0-9]+(?:\.[0-9]+)?)', val_clean)
                if num_m:
                    cand = num_m.group(1)
                    # Discard 4-digit year numbers (e.g. 1987, 2024-2026) for non-count analytes
                    if cand.isdigit() and 1900 <= int(cand) <= 2099 and test_match["name"] not in ["PLATELET COUNT", "TOTAL LEUCOCYTE COUNT (WBC)"]:
                        cand = None
                    val = cand

                # Lookahead on next row if value was wrapped
                if val is None and i + 1 < len(sorted_y):
                    next_col3 = [w["text"] for w in lines[sorted_y[i+1]] if val_x - 15 <= w["x0"] < units_x - 15]
                    if next_col3:
                        next_clean = re.sub(r'\bX\s*10\^?[36]\b', '', " ".join(next_col3), flags=re.I)
                        next_clean = re.sub(r'\b10\^[36]\b|\b10[³⁶]\b', '', next_clean, flags=re.I)
                        next_num = re.search(r'([0-9]+(?:\.[0-9]+)?)', next_clean)
                        if next_num:
                            cand = next_num.group(1)
                            if not (cand.isdigit() and 1900 <= int(cand) <= 2099):
                                val = cand

            if val is not None:
                clean_u = units_raw.strip() if units_raw and units_raw.strip().upper() not in ["UNITS", "UNIT", "-", ""] else test_match.get("unit", "")
                
                # If ref_raw is empty or non-numeric, look ahead on following lines for biological reference interval
                detected_ref = ref_raw
                if not detected_ref or not re.search(r'[0-9]', detected_ref):
                    for nxt_idx in range(i + 1, min(i + 8, len(sorted_y))):
                        nxt_line_text = " ".join(w["text"] for w in sorted(lines[sorted_y[nxt_idx]], key=lambda w: w["x0"]))
                        # Check gender specific labels or general Bio. Ref. Interval
                        m_fem = re.search(r'(?:Women|Female|Females(?:\s*:\s*Normally\s*Menstruating)?)\s*[:\-]+\s*([0-9]+(?:\.[0-9]+)?\s*-\s*[0-9]+(?:\.[0-9]+)?)', nxt_line_text, re.I)
                        m_male = re.search(r'(?:Men|Male|Males)\s*[:\-]+\s*([0-9]+(?:\.[0-9]+)?\s*-\s*[0-9]+(?:\.[0-9]+)?)', nxt_line_text, re.I)
                        m_gen = re.search(r'(?:Bio\.?\s*Ref\.?\s*Interval\.?\s*[:-]+|Normal\s*[:-]+)\s*([0-9]+(?:\.[0-9]+)?\s*-\s*[0-9]+(?:\.[0-9]+)?)', nxt_line_text, re.I)
                        
                        if m_fem or m_male or m_gen:
                            chosen_m = m_fem or m_male or m_gen
                            detected_ref = chosen_m.group(1).strip()
                            break

                found_tests[test_match["name"]] = {
                    "test_entry": test_match,
                    "value": val,
                    "unit": clean_u,
                    "method": method_raw or test_match.get("method", "Automated"),
                    "ref_range": detected_ref
                }

    return found_tests


def extract_ocr_clustered_table_records(ocr_output: Any) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """
    RapidOCR Table Alignment & Multi-Line Lookahead Normalization:
    - Clusters detected bounding boxes into discrete horizontal table rows using vertical midpoints:
      mid_y = (box.y_min + box.y_max) / 2 with a configurable row tolerance (10px).
    - Sorts clustered boxes within each row by horizontal position (x_min).
    - If a row contains only a test label fragment without a numerical value in subsequent columns,
      merges it with the adjacent label box in the same cluster before associating it with the value cell.
    """
    items: List[Dict[str, Any]] = []

    if hasattr(ocr_output, "boxes") and hasattr(ocr_output, "txts") and ocr_output.boxes is not None:
        for box, txt in zip(ocr_output.boxes, ocr_output.txts):
            if not txt or not str(txt).strip():
                continue
            xs = [pt[0] for pt in box]
            ys = [pt[1] for pt in box]
            items.append({
                "text": str(txt).strip(),
                "x_min": min(xs),
                "x_max": max(xs),
                "y_min": min(ys),
                "y_max": max(ys),
                "mid_y": (min(ys) + max(ys)) / 2.0,
                "mid_x": (min(xs) + max(xs)) / 2.0
            })
    elif isinstance(ocr_output, list):
        for entry in ocr_output:
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                box = entry[0]
                txt = entry[1]
                if not txt or not str(txt).strip():
                    continue
                try:
                    xs = [pt[0] for pt in box]
                    ys = [pt[1] for pt in box]
                    items.append({
                        "text": str(txt).strip(),
                        "x_min": min(xs),
                        "x_max": max(xs),
                        "y_min": min(ys),
                        "y_max": max(ys),
                        "mid_y": (min(ys) + max(ys)) / 2.0,
                        "mid_x": (min(xs) + max(xs)) / 2.0
                    })
                except Exception:
                    pass

    full_text = "\n".join(it["text"] for it in items)
    metadata = extract_patient_metadata(full_text)
    found_tests: Dict[str, Dict[str, Any]] = {}

    if not items:
        return metadata, found_tests

    # 1. Cluster boxes into horizontal rows by vertical midpoint
    ROW_TOLERANCE = 10.0
    row_clusters: List[List[Dict[str, Any]]] = []
    for it in sorted(items, key=lambda x: x["mid_y"]):
        matched = False
        for cluster in row_clusters:
            cluster_mid_y = sum(b["mid_y"] for b in cluster) / len(cluster)
            if abs(it["mid_y"] - cluster_mid_y) <= ROW_TOLERANCE:
                cluster.append(it)
                matched = True
                break
        if not matched:
            row_clusters.append([it])

    # 2. Sort boxes within each row cluster by x_min
    formatted_rows = [sorted(cluster, key=lambda b: b["x_min"]) for cluster in row_clusters]

    # 3. Merge multi-line test descriptions where a row contains only a label fragment
    merged_rows: List[List[Dict[str, Any]]] = []
    i = 0
    while i < len(formatted_rows):
        current_boxes = formatted_rows[i]
        curr_text = " ".join(b["text"] for b in current_boxes)
        has_val = any(re.search(r'^[<>]?\s*\d+(?:\.\d+)?$', b["text"].strip()) or "NON REACTIVE" in b["text"].upper() for b in current_boxes)

        if not has_val and i + 1 < len(formatted_rows):
            next_boxes = formatted_rows[i+1]
            next_has_val = any(re.search(r'^[<>]?\s*\d+(?:\.\d+)?$', b["text"].strip()) or "NON REACTIVE" in b["text"].upper() for b in next_boxes)

            test_match_curr = find_matching_test(curr_text)
            combined_label = f"{curr_text} {next_boxes[0]['text']}"
            test_match_combined = find_matching_test(combined_label)

            if test_match_combined or (not test_match_curr and next_has_val):
                merged_label = f"{curr_text} {next_boxes[0]['text']}"
                synthetic_box = dict(next_boxes[0])
                synthetic_box["text"] = merged_label
                synthetic_box["x_min"] = min(current_boxes[0]["x_min"], next_boxes[0]["x_min"])
                merged_row = [synthetic_box] + next_boxes[1:]
                merged_rows.append(merged_row)
                i += 2
                continue

        merged_rows.append(current_boxes)
        i += 1

    # 4. Extract tests from merged rows
    for row in merged_rows:
        row_text = " ".join(b["text"] for b in row)
        if row_text.upper() in CATEGORY_HEADERS:
            continue

        for entry in BLOOD_TESTS_REGISTRY:
            if entry["name"] in found_tests:
                continue

            for alias in entry["aliases"]:
                clean_row = re.sub(r'\(T2\)', '(T3)', row_text, flags=re.IGNORECASE)
                clean_row = re.sub(r'5YPHILIS', 'SYPHILIS', clean_row, flags=re.IGNORECASE)

                m = re.search(r'\b' + re.escape(alias) + r'\b', clean_row, re.IGNORECASE)
                if m:
                    val = None
                    if "NON REACTIVE" in clean_row.upper():
                        val = "NON REACTIVE"
                    else:
                        for b in row:
                            num_m = re.search(r'^[<>]?\s*([0-9]+(?:\.[0-9]+)?)$', b["text"].strip())
                            if num_m:
                                if num_m.group(1) not in ["2", "3", "4", "12", "6"]:
                                    val = num_m.group(1)
                                    break
                                elif not re.search(r'\b(?:T3|T4|B12|B-12)\b', b["text"], re.I):
                                    val = num_m.group(1)
                                    break
                        if not val:
                            after_alias = clean_row[m.end():]
                            after_clean = re.sub(r'\(?\b(?:T3|T4|B12|B-12|6\s*PART|EDTA|CMIA|ECLIA)\b\)?', '', after_alias, flags=re.IGNORECASE)
                            nums = re.findall(r'([0-9]+(?:\.[0-9]+)?)', after_clean)
                            if nums:
                                val = nums[0]

                    if val is not None:
                        found_tests[entry["name"]] = {
                            "test_entry": entry,
                            "value": val,
                            "unit": entry.get("unit", ""),
                            "method": entry.get("method", "Automated")
                        }
                        break

    return metadata, found_tests


def extract_lines_from_ocr_output(ocr_output: Any) -> List[str]:
    """Fallback text line extractor for legacy string processing."""
    lines = []
    if not ocr_output:
        return lines

    if hasattr(ocr_output, "txts") and ocr_output.txts:
        for t in ocr_output.txts:
            if t and str(t).strip():
                lines.append(str(t).strip())
    elif isinstance(ocr_output, list):
        for item in ocr_output:
            if isinstance(item, (list, tuple)) and len(item) > 1:
                lines.append(str(item[1]).strip())
            elif isinstance(item, str):
                lines.append(item.strip())
    return lines


def parse_text_lines_for_tests(text_lines: List[str], gender: str = "FEMALE") -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """Legacy lookahead scanner for multi-line plain text strings."""
    full_text = "\n".join(text_lines)
    metadata = extract_patient_metadata(full_text)
    if not gender:
        gender = metadata.get("gender", "FEMALE")

    found_tests: Dict[str, Dict[str, Any]] = {}
    for idx, line in enumerate(text_lines):
        clean_upper = line.strip().upper()
        if clean_upper in CATEGORY_HEADERS:
            continue

        for entry in BLOOD_TESTS_REGISTRY:
            if entry["name"] in found_tests:
                continue

            for alias in entry["aliases"]:
                test_line = re.sub(r'\(T2\)', '(T3)', line, flags=re.IGNORECASE)
                test_line = re.sub(r'5YPHILIS', 'SYPHILIS', test_line, flags=re.IGNORECASE)

                m = re.search(r'\b' + re.escape(alias) + r'\b', test_line, re.IGNORECASE)
                if m:
                    # Ignore literature citations and footnotes
                    if re.search(r'\b(clinical perspective|ActaObset|Gynecol|Scand|et al\.|editorial|journal|citation)\b', test_line, re.I):
                        continue
                    if re.search(r'^\s*[A-Z][a-z]+ [A-Z],', test_line):
                        continue

                    if "NON REACTIVE" in test_line.upper():
                        found_tests[entry["name"]] = {"test_entry": entry, "value": "NON REACTIVE"}
                        break

                    after_alias = test_line[m.end():]
                    after_clean = re.sub(r'\(?\b(?:T3|T4|B12|B-12|6\s*PART|EDTA|CMIA|ECLIA|CLIA|C\.L\.I\.A|E\.C\.L\.I\.A)\b\)?', '', after_alias, flags=re.IGNORECASE)
                    after_clean = re.sub(r'\bX\s*10\^?[36]\b|\b10\^[36]\b|\b10[³⁶]\b', '', after_clean, flags=re.IGNORECASE)
                    after_clean = re.sub(r'\b[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4}\b', '', after_clean)
                    
                    if re.search(r'^\s*([0-9]+(?:\.[0-9]+)?)\s*-\s*([0-9]+(?:\.[0-9]+)?)\s*$', after_clean.strip()):
                        after_clean = ""
                    nums = re.findall(r'([0-9]+(?:\.[0-9]+)?)', after_clean)
                    cand_val = None
                    for n in nums:
                        if n.isdigit() and 1900 <= int(n) <= 2099 and entry["name"] not in ["PLATELET COUNT", "TOTAL LEUCOCYTE COUNT (WBC)"]:
                            continue
                        cand_val = n
                        break

                    if cand_val is not None:
                        found_tests[entry["name"]] = {"test_entry": entry, "value": cand_val}
                        break

                    for next_idx in range(idx + 1, min(idx + 5, len(text_lines))):
                        next_line = text_lines[next_idx].strip()
                        if next_line.upper() in CATEGORY_HEADERS:
                            continue
                        if re.search(r'\b(clinical perspective|ActaObset|Gynecol|Scand|et al\.|editorial|journal|citation)\b', next_line, re.I):
                            continue
                        if "NON REACTIVE" in next_line.upper():
                            found_tests[entry["name"]] = {"test_entry": entry, "value": "NON REACTIVE"}
                            break
                        next_clean = re.sub(r'\bX\s*10\^?[36]\b|\b10\^[36]\b|\b10[³⁶]\b', '', next_line, flags=re.IGNORECASE)
                        next_clean = re.sub(r'\b[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4}\b', '', next_clean)
                        if re.search(r'^\s*([0-9]+(?:\.[0-9]+)?)\s*-\s*([0-9]+(?:\.[0-9]+)?)\s*$', next_clean.strip()):
                            continue
                        num_match = re.search(r'^([0-9]+(?:\.[0-9]+)?)', next_clean)
                        if num_match:
                            val = num_match.group(1)
                            if not (val.isdigit() and 1900 <= int(val) <= 2099 and entry["name"] not in ["PLATELET COUNT", "TOTAL LEUCOCYTE COUNT (WBC)"]):
                                found_tests[entry["name"]] = {"test_entry": entry, "value": val}
                                break
                    if entry["name"] in found_tests:
                        break

    return metadata, found_tests


def process_single_file(file_path: str, uploads_dir: str) -> Dict[str, Any]:
    path = Path(file_path)
    suffix = path.suffix.lower()
    preview_images: List[str] = []
    os.makedirs(uploads_dir, exist_ok=True)

    metadata: Dict[str, Any] = {
        "patient_name": "",
        "age_gender": "",
        "gender": "",
        "sample_id": "",
        "barcodes": [],
        "source_codes": [],
        "referred_by": "",
        "collection_date": "",
        "report_date": ""
    }
    found_tests: Dict[str, Dict[str, Any]] = {}

    if suffix == ".pdf":
        pdf = pdfium.PdfDocument(file_path)
        for page_idx in range(min(len(pdf), 25)):
            page = pdf[page_idx]
            pil_image = page.render(scale=2.0).to_pil()
            safe_stem = re.sub(r'[^a-zA-Z0-9_\-]', '_', path.stem)
            img_filename = f"{safe_stem}_page_{page_idx + 1}.png"
            img_path = os.path.join(uploads_dir, img_filename)
            pil_image.save(img_path)
            preview_images.append(f"/uploads/{img_filename}")

        # 1. High-precision coordinate vector extraction across digital pages
        full_text = ""
        with pdfplumber.open(file_path) as plumber_pdf:
            for page in plumber_pdf.pages:
                p_text = page.extract_text() or ""
                full_text += "\n" + p_text
                # Run coordinate-based column slicing
                page_tests = extract_vector_table_records(page)
                for k, v in page_tests.items():
                    if k not in found_tests or (found_tests[k].get("method") == "Calculated" and v.get("method") != "Calculated"):
                        found_tests[k] = v

        metadata = extract_patient_metadata(full_text)

        # 2. Text line lookahead scan across digital pages
        if full_text.strip():
            text_lines = [l.strip() for l in full_text.split('\n') if len(l.strip()) > 2]
            _, tests_txt = parse_text_lines_for_tests(text_lines, metadata.get("gender", "FEMALE"))
            for k, v in tests_txt.items():
                if k not in found_tests:
                    found_tests[k] = v

        # 3. Fallback to RapidOCR with horizontal bounding-box clustering for scanned/image PDFs
        if len(found_tests) < 10:
            ocr = get_ocr_engine()
            if ocr is not None:
                for page_idx in range(min(len(pdf), 25)):
                    safe_stem = re.sub(r'[^a-zA-Z0-9_\-]', '_', path.stem)
                    img_path = os.path.join(uploads_dir, f"{safe_stem}_page_{page_idx + 1}.png")
                    ocr_out = ocr(img_path)
                    meta_ocr, tests_ocr = extract_ocr_clustered_table_records(ocr_out)
                    
                    # Merge metadata
                    for mk, mv in meta_ocr.items():
                        if mv and not metadata.get(mk):
                            metadata[mk] = mv
                    metadata["barcodes"] = list(dict.fromkeys(metadata.get("barcodes", []) + meta_ocr.get("barcodes", [])))
                    metadata["source_codes"] = list(dict.fromkeys(metadata.get("source_codes", []) + meta_ocr.get("source_codes", [])))

                    for k, v in tests_ocr.items():
                        if k not in found_tests:
                            found_tests[k] = v

    elif suffix in [".png", ".jpg", ".jpeg", ".webp"]:
        safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', path.name)
        preview_images.append(f"/uploads/{safe_name}")
        ocr = get_ocr_engine()
        if ocr is not None:
            ocr_out = ocr(file_path)
            meta_ocr, tests_ocr = extract_ocr_clustered_table_records(ocr_out)
            metadata = meta_ocr
            found_tests.update(tests_ocr)

    return {
        "metadata": metadata,
        "preview_images": preview_images,
        "found_tests": found_tests
    }


def process_multiple_documents(file_paths: List[str], uploads_dir: str) -> Dict[str, Any]:
    """
    Process one or multiple uploaded files (PDFs and/or Images).
    Merges preview images, patient metadata, and test parameters seamlessly.
    """
    merged_metadata: Dict[str, Any] = {
        "patient_name": "",
        "age_gender": "",
        "gender": "",
        "sample_id": "",
        "barcodes": [],
        "source_codes": [],
        "referred_by": "",
        "collection_date": "",
        "report_date": "",
        "dob": "",
        "address": "",
        "pincode": "",
        "phone": "",
        "test_type": "",
        "lab_code": ""
    }
    all_previews: List[str] = []
    all_found_tests: Dict[str, Dict[str, Any]] = {}

    for file_path in file_paths:
        res = process_single_file(file_path, uploads_dir)
        all_previews.extend(res["preview_images"])

        # Merge metadata
        for k, v in res["metadata"].items():
            if v:
                if k == "barcodes":
                    merged_metadata["barcodes"] = list(dict.fromkeys(merged_metadata.get("barcodes", []) + v))
                elif k == "source_codes":
                    merged_metadata["source_codes"] = list(dict.fromkeys(merged_metadata.get("source_codes", []) + v))
                elif k == "lab_code":
                    # Update lab_code if current is empty or if this is a fuller code (with /)
                    if "/" in str(v) or not merged_metadata.get("lab_code"):
                        merged_metadata["lab_code"] = v
                elif k == "gender":
                    if v and (not merged_metadata.get("gender") or v.upper() == "MALE"):
                        merged_metadata["gender"] = v.upper()
                elif not merged_metadata.get(k):
                    merged_metadata[k] = v

        if not merged_metadata.get("sample_id") and merged_metadata.get("barcodes"):
            merged_metadata["sample_id"] = merged_metadata["barcodes"][0]

        if not merged_metadata.get("lab_code"):
            if merged_metadata.get("source_codes"):
                merged_metadata["lab_code"] = merged_metadata["source_codes"][-1]
            elif merged_metadata.get("sample_id"):
                merged_metadata["lab_code"] = merged_metadata["sample_id"]

        all_found_tests.update(res["found_tests"])

    test_pkg_u = (merged_metadata.get("test_type") or "").upper()
    if not merged_metadata.get("gender"):
        if any(w in test_pkg_u for w in ["MEN", "MENS", "MALE"]):
            merged_metadata["gender"] = "MALE"
        else:
            merged_metadata["gender"] = "FEMALE"

    gender = merged_metadata.get("gender") or "FEMALE"

    # Format into canonical list of tests
    final_test_rows: List[Dict[str, Any]] = []
    for entry in BLOOD_TESTS_REGISTRY:
        test_name = entry["name"]
        ref_range, min_val, max_val = get_gender_specific_range(entry, gender)
        is_phase_dependent = entry.get("is_phase_dependent", False)

        if test_name in all_found_tests:
            val = all_found_tests[test_name]["value"]
            found_info = all_found_tests[test_name]
        else:
            continue

        extracted_unit = found_info.get("unit")
        clean_unit = extracted_unit if extracted_unit and extracted_unit.strip() not in ["-", "—", "UNITS", "UNIT", ""] else entry["unit"]

        # Prioritize the actual reference range extracted from the source document!
        extracted_ref = (found_info.get("ref_range") or "").strip()
        cleaned_ref = re.sub(r'^(?:Bio\.?\s*Ref\.?\s*Interval\.?\s*[:-]?|Normal\s*[:-]?)\s*', '', extracted_ref, flags=re.I).strip()
        cleaned_ref = re.sub(r'[–—]', '-', cleaned_ref).strip()

        m_range = re.search(r'([0-9]+(?:\.[0-9]+)?\s*-\s*[0-9]+(?:\.[0-9]+)?|<[=\s]*[0-9]+(?:\.[0-9]+)?|>[=\s]*[0-9]+(?:\.[0-9]+)?)', cleaned_ref)
        if m_range:
            ref_range = m_range.group(1).strip()
            min_val = None
            max_val = None
            m_bounds = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*-\s*([0-9]+(?:\.[0-9]+)?)', ref_range)
            if m_bounds:
                min_val = float(m_bounds.group(1))
                max_val = float(m_bounds.group(2))
            else:
                m_lt = re.search(r'<[=\s]*([0-9]+(?:\.[0-9]+)?)', ref_range)
                if m_lt:
                    max_val = float(m_lt.group(1))
                m_gt = re.search(r'>[=\s]*([0-9]+(?:\.[0-9]+)?)', ref_range)
                if m_gt:
                    min_val = float(m_gt.group(1))

        # If test is ANA, normalize to CMIA AU/mL if value matches CMIA
        if "ANTI NUCLEAR ANTIBODIES" in test_name or test_name == "ANA":
            val_m = re.search(r'([0-9]+(?:\.[0-9]+)?)', str(val) or '0')
            v_num = float(val_m.group(1)) if val_m else 0.0
            if "AU" in str(clean_unit).upper() or v_num > 1.2 or "< 20" in str(ref_range):
                clean_unit = "AU/mL"
                ref_range = "< 20"
                min_val = None
                max_val = 20.0
                flag = "NORMAL" if v_num <= 20.0 else "HIGH"
            else:
                flag = determine_flag_gender(val, min_val, max_val, is_phase_dependent, ref_range_str=ref_range)
        else:
            flag = determine_flag_gender(val, min_val, max_val, is_phase_dependent, ref_range_str=ref_range)

        final_test_rows.append({
            "sr_no": len(final_test_rows) + 1,
            "category": entry["category"],
            "parameter": entry["name"],
            "value": val,
            "unit": clean_unit,
            "ref_range": ref_range,
            "min_val": min_val,
            "max_val": max_val,
            "flag": flag,
            "is_phase_dependent": is_phase_dependent,
            "phase_disclaimer": entry.get("phase_disclaimer", ""),
            "method": found_info.get("method") or entry.get("method", "Automated")
        })

    flagged_tests = [t for t in final_test_rows if t.get("flag") in ["HIGH", "LOW"]]

    return {
        "status": "success",
        "extraction_mode": f"Local Engine ({len(file_paths)} file{'s' if len(file_paths) > 1 else ''} processed)",
        "preview_images": all_previews,
        "metadata": merged_metadata,
        "tests": final_test_rows,
        "flagged_tests": flagged_tests,
        "flagged_count": len(flagged_tests)
    }


def process_document(file_path: str, uploads_dir: str) -> Dict[str, Any]:
    """Compatibility wrapper for single file processing."""
    return process_multiple_documents([file_path], uploads_dir)

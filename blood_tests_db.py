"""
Clinical Blood Test Reference Database with Gender-Specific Normal Ranges.
Provides precise biological reference intervals for Males vs Females across all 53 diagnostic parameters.
"""

from typing import Dict, Any, Optional, List, Tuple
import re

BLOOD_TESTS_REGISTRY: List[Dict[str, Any]] = [
    # 1. INFERTILITY & PITUITARY
    {
        "category": "INFERTILITY",
        "name": "FOLLICLE STIMULATING HORMONE (FSH)",
        "aliases": ["fsh", "follicle stimulating hormone"],
        "unit": "mIU/mL",
        "ref_range_male": "1.5 - 12.4",
        "min_val_male": 1.5,
        "max_val_male": 12.4,
        "ref_range_female": "Follicular: 3.5 - 12.5 | Mid-cycle: 4.7 - 21.5 | Luteal: 1.7 - 7.7 | Postmenopausal: 25.8 - 134.8",
        "min_val_female": 1.5,
        "max_val_female": 134.8,
        "is_phase_dependent": True,
        "phase_intervals": {
            "Follicular": (3.5, 12.5),
            "Mid-cycle": (4.7, 21.5),
            "Luteal": (1.7, 7.7),
            "Postmenopausal": (25.8, 134.8)
        },
        "phase_disclaimer": "Values vary significantly by menstrual cycle phase. Clinical correlation with cycle day recommended.",
        "method": "E.C.L.I.A"
    },
    {
        "category": "INFERTILITY",
        "name": "SEX HORMONE BINDING GLOBULIN (SHBG)",
        "aliases": ["shbg", "sex hormone binding globulin"],
        "unit": "nmol/L",
        "ref_range_male": "10 - 57",
        "min_val_male": 10.0,
        "max_val_male": 57.0,
        "ref_range_female": "18 - 144", # Non-pregnant female: 18 - 144 nmol/L
        "min_val_female": 18.0,
        "max_val_female": 144.0,
        "is_phase_dependent": False,
        "method": "C.L.I.A"
    },
    {
        "category": "INFERTILITY",
        "name": "LUTEINISING HORMONE (LH)",
        "aliases": ["lh", "luteinising hormone", "luteinizing hormone"],
        "unit": "mIU/mL",
        "ref_range_male": "1.7 - 8.6",
        "min_val_male": 1.7,
        "max_val_male": 8.6,
        "ref_range_female": "Follicular: 2.4 - 12.6 | Mid-cycle: 14.0 - 95.6 | Luteal: 1.0 - 11.4 | Postmenopausal: 7.7 - 58.5",
        "min_val_female": 1.0,
        "max_val_female": 95.6,
        "is_phase_dependent": True,
        "phase_intervals": {
            "Follicular": (2.4, 12.6),
            "Mid-cycle": (14.0, 95.6),
            "Luteal": (1.0, 11.4),
            "Postmenopausal": (7.7, 58.5)
        },
        "phase_disclaimer": "Values vary significantly across menstrual cycle phases.",
        "method": "E.C.L.I.A"
    },
    {
        "category": "INFERTILITY",
        "name": "PROLACTIN (PRL)",
        "aliases": ["prolactin", "prl", "prolactin (prl)"],
        "unit": "ng/mL",
        "ref_range_male": "4.04 - 15.2",
        "min_val_male": 4.04,
        "max_val_male": 15.2,
        "ref_range_female": "4.79 - 23.3",
        "min_val_female": 4.79,
        "max_val_female": 23.3,
        "method": "E.C.L.I.A"
    },
    {
        "category": "INFERTILITY",
        "name": "PROGESTERONE",
        "aliases": ["progesterone", "prg", "serum progesterone"],
        "unit": "ng/mL",
        "ref_range_male": "0.1 - 0.8",
        "min_val_male": 0.1,
        "max_val_male": 0.8,
        "ref_range_female": "Follicular: 0.1 - 1.5 | Luteal: 1.7 - 27.0 | Postmenopausal: 0.1 - 0.8",
        "min_val_female": 0.1,
        "max_val_female": 27.0,
        "is_phase_dependent": True,
        "phase_intervals": {
            "Follicular": (0.1, 1.5),
            "Luteal": (1.7, 27.0),
            "Postmenopausal": (0.1, 0.8)
        },
        "phase_disclaimer": "Diagnostic marker for ovulation timing and corpus luteum function.",
        "method": "C.L.I.A"
    },
    {
        "category": "MALE ANDROGEN & STEROID HORMONES",
        "name": "DIHYDROTESTOSTERONE (DHT)",
        "aliases": ["dihydrotestosterone", "dht", "dihydrotestosterone (dht)", "serum dht"],
        "unit": "pg/mL",
        "ref_range_male": "143 - 842",
        "min_val_male": 143.0,
        "max_val_male": 842.0,
        "ref_range_female": "0 - 596",
        "min_val_female": 0.0,
        "max_val_female": 596.0,
        "method": "E.C.L.I.A"
    },

    # 2. METABOLIC
    {
        "category": "METABOLIC",
        "name": "MAGNESIUM",
        "aliases": ["magnesium", "serum magnesium", "mg"],
        "unit": "mg/dL",
        "ref_range_male": "1.90 - 3.10",
        "min_val_male": 1.90,
        "max_val_male": 3.10,
        "ref_range_female": "1.9 - 2.5",
        "min_val_female": 1.9,
        "max_val_female": 2.5,
        "method": "PHOTOMETRY"
    },
    {
        "category": "METABOLIC",
        "name": "CORTISOL",
        "aliases": ["cortisol", "serum cortisol"],
        "unit": "µg/dL",
        "ref_range_male": "6.00am to 10am: 6.7 - 22.6 | 4.00pm to 8pm: < 10.0",
        "min_val_male": 6.7,
        "max_val_male": 22.6,
        "ref_range_female": "6.00am to 10am: 6.7 - 22.6 | 4.00pm to 8pm: < 10.0",
        "min_val_female": 6.7,
        "max_val_female": 22.6,
        "method": "C.L.I.A"
    },

    # 3. VITAMINS
    {
        "category": "VITAMINS",
        "name": "25-OH VITAMIN D (TOTAL)",
        "aliases": ["25-oh vitamin d", "vitamin d", "vit d", "25-hydroxy vitamin d"],
        "unit": "ng/mL",
        "ref_range_male": "30 - 100",
        "min_val_male": 30.0,
        "max_val_male": 100.0,
        "ref_range_female": "30 - 100",
        "min_val_female": 30.0,
        "max_val_female": 100.0,
        "method": "C.M.I.A"
    },
    {
        "category": "VITAMINS",
        "name": "VITAMIN B-12",
        "aliases": ["vitamin b-12", "vitamin b12", "b12", "cyanocobalamin"],
        "unit": "pg/mL",
        "ref_range_male": "211 - 911",
        "min_val_male": 211.0,
        "max_val_male": 911.0,
        "ref_range_female": "197 - 771",
        "min_val_female": 197.0,
        "max_val_female": 771.0,
        "method": "E.C.L.I.A"
    },

    # 4. CARDIAC RISK MARKERS
    {
        "category": "CARDIAC RISK MARKERS",
        "name": "C-REACTIVE PROTEIN (CRP)",
        "aliases": ["c-reactive protein", "crp", "hs-crp"],
        "unit": "mg/L",
        "ref_range_male": "0.0 - 5.0",
        "min_val_male": 0.0,
        "max_val_male": 5.0,
        "ref_range_female": "0.0 - 5.0",
        "min_val_female": 0.0,
        "max_val_female": 5.0,
        "method": "IMMUNOTURBIDIMETRY"
    },

    # 5. ARTHRITIS
    {
        "category": "ARTHRITIS",
        "name": "ANTI NUCLEAR ANTIBODIES (ANA)",
        "aliases": ["anti nuclear antibodies", "ana", "ana cmia", "ana elisa"],
        "unit": "AU/mL",
        "ref_range_male": "< 20",
        "min_val_male": None,
        "max_val_male": 20.0,
        "ref_range_female": "< 20",
        "min_val_female": None,
        "max_val_female": 20.0,
        "method": "C.M.I.A"
    },
    {
        "category": "ARTHRITIS",
        "name": "PHOSPHOROUS",
        "aliases": ["phosphorous", "phosphorus", "serum phosphorus", "phosphate"],
        "unit": "mg/dL",
        "ref_range_male": "2.4 - 5.1",
        "min_val_male": 2.4,
        "max_val_male": 5.1,
        "ref_range_female": "2.4 - 5.1",
        "min_val_female": 2.4,
        "max_val_female": 5.1,
        "method": "PHOTOMETRY"
    },
    {
        "category": "INFECTIOUS / INFLAMMATORY",
        "name": "ERYTHROCYTE SEDIMENTATION RATE (ESR)",
        "aliases": ["erythrocyte sedimentation rate", "esr", "erythrocyte sedimentation rate (esr)", "esr westergren"],
        "unit": "mm/hr",
        "ref_range_male": "0 - 15",
        "min_val_male": 0.0,
        "max_val_male": 15.0,
        "ref_range_female": "0 - 20",
        "min_val_female": 0.0,
        "max_val_female": 20.0,
        "method": "WESTERGREN"
    },
    {
        "category": "ARTHRITIS",
        "name": "RHEUMATOID FACTOR (RF)",
        "aliases": ["rheumatoid factor", "rf", "rheumatoid factor (rf)", "rheumatoid factor (rf) / inflammatory screen"],
        "unit": "IU/mL",
        "ref_range_male": "< 14.0",
        "min_val_male": 0.0,
        "max_val_male": 14.0,
        "ref_range_female": "< 14.0",
        "min_val_female": 0.0,
        "max_val_female": 14.0,
        "method": "IMMUNOTURBIDIMETRY"
    },

    # 6. IRON DEFICIENCY / ANEMIA PROFILE
    {
        "category": "IRON DEFICIENCY",
        "name": "IRON",
        "aliases": ["iron", "serum iron", "fe"],
        "unit": "µg/dL",
        "ref_range_male": "65 - 175",
        "min_val_male": 65.0,
        "max_val_male": 175.0,
        "ref_range_female": "50 - 170",
        "min_val_female": 50.0,
        "max_val_female": 170.0,
        "method": "PHOTOMETRY"
    },
    {
        "category": "IRON DEFICIENCY",
        "name": "TOTAL IRON BINDING CAPACITY (TIBC)",
        "aliases": ["total iron binding capacity", "tibc"],
        "unit": "µg/dL",
        "ref_range_male": "225 - 535",
        "min_val_male": 225.0,
        "max_val_male": 535.0,
        "ref_range_female": "215 - 535",
        "min_val_female": 215.0,
        "max_val_female": 535.0,
        "method": "PHOTOMETRY"
    },
    {
        "category": "IRON DEFICIENCY",
        "name": "% TRANSFERRIN SATURATION",
        "aliases": ["% transferrin saturation", "transferrin saturation"],
        "unit": "%",
        "ref_range_male": "13 - 45",
        "min_val_male": 13.0,
        "max_val_male": 45.0,
        "ref_range_female": "13 - 45",
        "min_val_female": 13.0,
        "max_val_female": 45.0,
        "method": "CALCULATED"
    },
    {
        "category": "IRON DEFICIENCY",
        "name": "UNSAT. IRON-BINDING CAPACITY (UIBC)",
        "aliases": ["unsat. iron-binding capacity", "unsat.iron-binding capacity", "unsat.iron-binding", "uibc", "unsaturated iron binding capacity"],
        "unit": "µg/dL",
        "ref_range_male": "162 - 368",
        "min_val_male": 162.0,
        "max_val_male": 368.0,
        "ref_range_female": "162 - 368",
        "min_val_female": 162.0,
        "max_val_female": 368.0,
        "method": "PHOTOMETRY"
    },
    {
        "category": "IRON DEFICIENCY",
        "name": "FERRITIN",
        "aliases": ["ferritin", "serum ferritin"],
        "unit": "ng/mL",
        "ref_range_male": "21.81 - 274.66",
        "min_val_male": 21.81,
        "max_val_male": 274.66,
        "ref_range_female": "4.63 - 204.00",
        "min_val_female": 4.63,
        "max_val_female": 204.00,
        "method": "C.M.I.A"
    },

    # 7. ELEMENTS
    {
        "category": "ELEMENTS",
        "name": "SERUM ZINC",
        "aliases": ["serum zinc", "zinc", "zn"],
        "unit": "µg/dL",
        "ref_range_male": "70 - 115",
        "min_val_male": 70.0,
        "max_val_male": 115.0,
        "ref_range_female": "70 - 115",
        "min_val_female": 70.0,
        "max_val_female": 115.0,
        "method": "PHOTOMETRY"
    },

    # 8. HORMONE
    {
        "category": "HORMONE",
        "name": "TESTOSTERONE",
        "aliases": ["testosterone", "total testosterone", "serum testosterone"],
        "unit": "ng/dL",
        "ref_range_male": "240 - 950",
        "min_val_male": 240.0,
        "max_val_male": 950.0,
        "ref_range_female": "6 - 82",
        "min_val_female": 6.0,
        "max_val_female": 82.0,
        "method": "E.C.L.I.A"
    },

    # 9. INFECTIOUS DISEASE
    {
        "category": "INFECTIOUS DISEASE",
        "name": "VDRL (RPR) FOR SYPHILIS",
        "aliases": ["vdrl", "rpr", "vdrl (rpr) for syphilis"],
        "unit": "-",
        "ref_range_male": "NON REACTIVE",
        "min_val_male": None,
        "max_val_male": None,
        "ref_range_female": "NON REACTIVE",
        "min_val_female": None,
        "max_val_female": None,
        "method": "FLOCCULATION"
    },

    # 10. RENAL
    {
        "category": "RENAL",
        "name": "CALCIUM",
        "aliases": ["calcium", "serum calcium", "ca"],
        "unit": "mg/dL",
        "ref_range_male": "8.8 - 10.6",
        "min_val_male": 8.8,
        "max_val_male": 10.6,
        "ref_range_female": "8.6 - 10.3",
        "min_val_female": 8.6,
        "max_val_female": 10.3,
        "method": "PHOTOMETRY"
    },

    # 11. THYROID
    {
        "category": "THYROID",
        "name": "TOTAL TRIIODOTHYRONINE (T3)",
        "aliases": ["total triiodothyronine", "total t3", "t3"],
        "unit": "ng/dL",
        "ref_range_male": "58 - 159",
        "min_val_male": 58.0,
        "max_val_male": 159.0,
        "ref_range_female": "58 - 159",
        "min_val_female": 58.0,
        "max_val_female": 159.0,
        "method": "C.M.I.A"
    },
    {
        "category": "THYROID",
        "name": "TOTAL THYROXINE (T4)",
        "aliases": ["total thyroxine", "total t4", "t4"],
        "unit": "µg/dL",
        "ref_range_male": "4.87 - 11.72",
        "min_val_male": 4.87,
        "max_val_male": 11.72,
        "ref_range_female": "4.87 - 11.72",
        "min_val_female": 4.87,
        "max_val_female": 11.72,
        "method": "C.M.I.A"
    },
    {
        "category": "THYROID",
        "name": "TSH - ULTRASENSITIVE",
        "aliases": ["tsh - ultrasensitive", "tsh", "thyroid stimulating hormone"],
        "unit": "µIU/mL",
        "ref_range_male": "0.35 - 4.94",
        "min_val_male": 0.35,
        "max_val_male": 4.94,
        "ref_range_female": "0.35 - 4.94",
        "min_val_female": 0.35,
        "max_val_female": 4.94,
        "method": "C.M.I.A"
    },

    # 12. COMPLETE HEMOGRAM / CBC
    {
        "category": "COMPLETE HEMOGRAM",
        "name": "HEMOGLOBIN",
        "aliases": ["hemoglobin", "hb", "haemoglobin"],
        "unit": "g/dL",
        "ref_range_male": "13.0 - 17.0",
        "min_val_male": 13.0,
        "max_val_male": 17.0,
        "ref_range_female": "12.0 - 15.0",
        "min_val_female": 12.0,
        "max_val_female": 15.0,
        "method": "SLS-Hemoglobin Method"
    },
    {
        "category": "COMPLETE HEMOGRAM",
        "name": "HEMATOCRIT (PCV)",
        "aliases": ["hematocrit", "pcv", "packed cell volume"],
        "unit": "%",
        "ref_range_male": "40.0 - 50.0",
        "min_val_male": 40.0,
        "max_val_male": 50.0,
        "ref_range_female": "36.0 - 46.0",
        "min_val_female": 36.0,
        "max_val_female": 46.0,
        "method": "CPH Detection"
    },
    {
        "category": "COMPLETE HEMOGRAM",
        "name": "TOTAL RBC",
        "aliases": ["total rbc", "rbc count", "red blood cell count"],
        "unit": "X 10^6 / µL",
        "ref_range_male": "4.5 - 5.5",
        "min_val_male": 4.5,
        "max_val_male": 5.5,
        "ref_range_female": "3.8 - 4.8",
        "min_val_female": 3.8,
        "max_val_female": 4.8,
        "method": "HF & EI"
    },
    {
        "category": "COMPLETE HEMOGRAM",
        "name": "MEAN CORPUSCULAR VOLUME (MCV)",
        "aliases": ["mcv", "mean corpuscular volume"],
        "unit": "fL",
        "ref_range_male": "83.0 - 101.0",
        "min_val_male": 83.0,
        "max_val_male": 101.0,
        "ref_range_female": "83.0 - 101.0",
        "min_val_female": 83.0,
        "max_val_female": 101.0,
        "method": "Calculated"
    },
    {
        "category": "COMPLETE HEMOGRAM",
        "name": "MEAN CORPUSCULAR HEMOGLOBIN (MCH)",
        "aliases": ["mch", "mean corpuscular hemoglobin"],
        "unit": "pg",
        "ref_range_male": "27.0 - 32.0",
        "min_val_male": 27.0,
        "max_val_male": 32.0,
        "ref_range_female": "27.0 - 32.0",
        "min_val_female": 27.0,
        "max_val_female": 32.0,
        "method": "Calculated"
    },
    {
        "category": "COMPLETE HEMOGRAM",
        "name": "MEAN CORP. HEMO. CONC (MCHC)",
        "aliases": ["mchc", "mean corp. hemo. conc", "mean corpuscular hemoglobin concentration"],
        "unit": "g/dL",
        "ref_range_male": "31.5 - 34.5",
        "min_val_male": 31.5,
        "max_val_male": 34.5,
        "ref_range_female": "31.5 - 34.5",
        "min_val_female": 31.5,
        "max_val_female": 34.5,
        "method": "Calculated"
    },
    {
        "category": "COMPLETE HEMOGRAM",
        "name": "RED CELL DISTRIBUTION WIDTH - SD (RDW-SD)",
        "aliases": ["rdw-sd", "red cell distribution width - sd"],
        "unit": "fL",
        "ref_range_male": "39.0 - 46.0",
        "min_val_male": 39.0,
        "max_val_male": 46.0,
        "ref_range_female": "39.0 - 46.0",
        "min_val_female": 39.0,
        "max_val_female": 46.0,
        "method": "Calculated"
    },
    {
        "category": "COMPLETE HEMOGRAM",
        "name": "RED CELL DISTRIBUTION WIDTH (RDW - CV)",
        "aliases": ["rdw-cv", "rdw - cv", "red cell distribution width"],
        "unit": "%",
        "ref_range_male": "11.6 - 14.0",
        "min_val_male": 11.6,
        "max_val_male": 14.0,
        "ref_range_female": "11.6 - 14.0",
        "min_val_female": 11.6,
        "max_val_female": 14.0,
        "method": "Calculated"
    },
    {
        "category": "COMPLETE HEMOGRAM",
        "name": "RED CELL DISTRIBUTION WIDTH INDEX (RDWI)",
        "aliases": ["rdwi", "red cell distribution width index"],
        "unit": "-",
        "ref_range_male": "*Refer Note below",
        "min_val_male": None,
        "max_val_male": None,
        "ref_range_female": "*Refer Note below",
        "min_val_female": None,
        "max_val_female": None,
        "method": "Calculated"
    },
    {
        "category": "COMPLETE HEMOGRAM",
        "name": "MENTZER INDEX",
        "aliases": ["mentzer index", "mi"],
        "unit": "-",
        "ref_range_male": "*Refer Note below",
        "min_val_male": None,
        "max_val_male": None,
        "ref_range_female": "*Refer Note below",
        "min_val_female": None,
        "max_val_female": None,
        "method": "Calculated"
    },
    {
        "category": "COMPLETE HEMOGRAM",
        "name": "TOTAL LEUCOCYTE COUNT (WBC)",
        "aliases": ["total leucocyte count (wbc)", "wbc", "total wbc count"],
        "unit": "X 10³ / µL",
        "ref_range_male": "4.0 - 10.0",
        "min_val_male": 4.0,
        "max_val_male": 10.0,
        "ref_range_female": "4.0 - 10.0",
        "min_val_female": 4.0,
        "max_val_female": 10.0,
        "method": "HF & FC"
    },

    # DIFFERENTIAL LEUCOCYTE COUNT
    {
        "category": "DIFFERENTIAL LEUCOCYTE COUNT",
        "name": "NEUTROPHILS",
        "aliases": ["neutrophils", "neutrophils percentage"],
        "unit": "%",
        "ref_range_male": "40 - 80",
        "min_val_male": 40.0,
        "max_val_male": 80.0,
        "ref_range_female": "40 - 80",
        "min_val_female": 40.0,
        "max_val_female": 80.0,
        "method": "Flow Cytometry"
    },
    {
        "category": "DIFFERENTIAL LEUCOCYTE COUNT",
        "name": "LYMPHOCYTES",
        "aliases": ["lymphocytes", "lymphocyte", "lymphocytes percentage"],
        "unit": "%",
        "ref_range_male": "20 - 40",
        "min_val_male": 20.0,
        "max_val_male": 40.0,
        "ref_range_female": "20 - 40",
        "min_val_female": 20.0,
        "max_val_female": 40.0,
        "method": "Flow Cytometry"
    },
    {
        "category": "DIFFERENTIAL LEUCOCYTE COUNT",
        "name": "MONOCYTES",
        "aliases": ["monocytes", "monocytes percentage"],
        "unit": "%",
        "ref_range_male": "2 - 10",
        "min_val_male": 2.0,
        "max_val_male": 10.0,
        "ref_range_female": "2 - 10",
        "min_val_female": 2.0,
        "max_val_female": 10.0,
        "method": "Flow Cytometry"
    },
    {
        "category": "DIFFERENTIAL LEUCOCYTE COUNT",
        "name": "EOSINOPHILS",
        "aliases": ["eosinophils", "eosinophils percentage"],
        "unit": "%",
        "ref_range_male": "1 - 6",
        "min_val_male": 1.0,
        "max_val_male": 6.0,
        "ref_range_female": "1 - 6",
        "min_val_female": 1.0,
        "max_val_female": 6.0,
        "method": "Flow Cytometry"
    },
    {
        "category": "DIFFERENTIAL LEUCOCYTE COUNT",
        "name": "BASOPHILS",
        "aliases": ["basophils", "basophils percentage"],
        "unit": "%",
        "ref_range_male": "0 - 2",
        "min_val_male": 0.0,
        "max_val_male": 2.0,
        "ref_range_female": "0 - 2",
        "min_val_female": 0.0,
        "max_val_female": 2.0,
        "method": "Flow Cytometry"
    },
    {
        "category": "DIFFERENTIAL LEUCOCYTE COUNT",
        "name": "IMMATURE GRANULOCYTE PERCENTAGE (IG%)",
        "aliases": ["immature granulocyte percentage (ig%)", "immature granulocytes percentage", "ig%"],
        "unit": "%",
        "ref_range_male": "0.0 - 0.5",
        "min_val_male": 0.0,
        "max_val_male": 0.5,
        "ref_range_female": "0.0 - 0.4",
        "min_val_female": 0.0,
        "max_val_female": 0.4,
        "method": "Flow Cytometry"
    },
    {
        "category": "DIFFERENTIAL LEUCOCYTE COUNT",
        "name": "NUCLEATED RED BLOOD CELLS %",
        "aliases": ["nucleated red blood cells %", "nrbc %"],
        "unit": "%",
        "ref_range_male": "0.0 - 5.0",
        "min_val_male": 0.0,
        "max_val_male": 5.0,
        "ref_range_female": "0.0 - 5.0",
        "min_val_female": 0.0,
        "max_val_female": 5.0,
        "method": "Flow Cytometry"
    },

    # ABSOLUTE LEUCOCYTE COUNT
    {
        "category": "ABSOLUTE LEUCOCYTE COUNT",
        "name": "NEUTROPHILS - ABSOLUTE COUNT",
        "aliases": ["neutrophils - absolute count", "absolute neutrophil count", "anc"],
        "unit": "X 10³ / µL",
        "ref_range_male": "2.0 - 7.0",
        "min_val_male": 2.0,
        "max_val_male": 7.0,
        "ref_range_female": "2.0 - 7.0",
        "min_val_female": 2.0,
        "max_val_female": 7.0,
        "method": "Calculated"
    },
    {
        "category": "ABSOLUTE LEUCOCYTE COUNT",
        "name": "LYMPHOCYTES - ABSOLUTE COUNT",
        "aliases": ["lymphocytes - absolute count", "absolute lymphocyte count", "alc"],
        "unit": "X 10³ / µL",
        "ref_range_male": "1.0 - 3.0",
        "min_val_male": 1.0,
        "max_val_male": 3.0,
        "ref_range_female": "1.0 - 3.0",
        "min_val_female": 1.0,
        "max_val_female": 3.0,
        "method": "Calculated"
    },
    {
        "category": "ABSOLUTE LEUCOCYTE COUNT",
        "name": "MONOCYTES - ABSOLUTE COUNT",
        "aliases": ["monocytes - absolute count", "absolute monocyte count"],
        "unit": "X 10³ / µL",
        "ref_range_male": "0.2 - 1.0",
        "min_val_male": 0.2,
        "max_val_male": 1.0,
        "ref_range_female": "0.2 - 1.0",
        "min_val_female": 0.2,
        "max_val_female": 1.0,
        "method": "Calculated"
    },
    {
        "category": "ABSOLUTE LEUCOCYTE COUNT",
        "name": "BASOPHILS - ABSOLUTE COUNT",
        "aliases": ["basophils - absolute count", "absolute basophil count"],
        "unit": "X 10³ / µL",
        "ref_range_male": "0.02 - 0.1",
        "min_val_male": 0.02,
        "max_val_male": 0.1,
        "ref_range_female": "0.02 - 0.1",
        "min_val_female": 0.02,
        "max_val_female": 0.1,
        "method": "Calculated"
    },
    {
        "category": "ABSOLUTE LEUCOCYTE COUNT",
        "name": "EOSINOPHILS - ABSOLUTE COUNT",
        "aliases": ["eosinophils - absolute count", "absolute eosinophil count", "aec"],
        "unit": "X 10³ / µL",
        "ref_range_male": "0.02 - 0.5",
        "min_val_male": 0.02,
        "max_val_male": 0.5,
        "ref_range_female": "0.02 - 0.5",
        "min_val_female": 0.02,
        "max_val_female": 0.5,
        "method": "Calculated"
    },
    {
        "category": "ABSOLUTE LEUCOCYTE COUNT",
        "name": "IMMATURE GRANULOCYTES (IG)",
        "aliases": ["immature granulocytes (ig)", "immature granulocytes - absolute count", "immature granulocytes - absolute count (ig#)", "immature granulocyte count", "ig#", "ig"],
        "unit": "X 10³ / µL",
        "ref_range_male": "0.0 - 0.3",
        "min_val_male": 0.0,
        "max_val_male": 0.3,
        "ref_range_female": "0.0 - 0.3",
        "min_val_female": 0.0,
        "max_val_female": 0.3,
        "method": "Calculated"
    },
    {
        "category": "ABSOLUTE LEUCOCYTE COUNT",
        "name": "NUCLEATED RED BLOOD CELLS",
        "aliases": ["nucleated red blood cells", "nucleated red blood cells - absolute count", "nucleated red blood cells - absolute count (nrbc#)", "absolute nrbc", "nrbc#"],
        "unit": "X 10³ / µL",
        "ref_range_male": "0.0 - 0.5",
        "min_val_male": 0.0,
        "max_val_male": 0.5,
        "ref_range_female": "0.0 - 0.5",
        "min_val_female": 0.0,
        "max_val_female": 0.5,
        "method": "Calculated"
    },

    # PLATELET COUNT & INDICES
    {
        "category": "PLATELET COUNT & INDICES",
        "name": "PLATELET COUNT",
        "aliases": ["platelet count", "platelets", "total platelets"],
        "unit": "X 10³ / µL",
        "ref_range_male": "150 - 410",
        "min_val_male": 150.0,
        "max_val_male": 410.0,
        "ref_range_female": "150 - 410",
        "min_val_female": 150.0,
        "max_val_female": 410.0,
        "method": "HF & EI"
    },
    {
        "category": "PLATELET COUNT & INDICES",
        "name": "MEAN PLATELET VOLUME (MPV)",
        "aliases": ["mean platelet volume (mpv)", "mpv"],
        "unit": "fL",
        "ref_range_male": "6.5 - 12.0",
        "min_val_male": 6.5,
        "max_val_male": 12.0,
        "ref_range_female": "6.5 - 12.0",
        "min_val_female": 6.5,
        "max_val_female": 12.0,
        "method": "Calculated"
    },
    {
        "category": "PLATELET COUNT & INDICES",
        "name": "PLATELET DISTRIBUTION WIDTH (PDW)",
        "aliases": ["platelet distribution width (pdw)", "pdw"],
        "unit": "fL",
        "ref_range_male": "9.6 - 15.2",
        "min_val_male": 9.6,
        "max_val_male": 15.2,
        "ref_range_female": "9.6 - 15.2",
        "min_val_female": 9.6,
        "max_val_female": 15.2,
        "method": "Calculated"
    },
    {
        "category": "PLATELET COUNT & INDICES",
        "name": "PLATELET TO LARGE CELL RATIO (PLCR)",
        "aliases": ["platelet to large cell ratio (plcr)", "platelet large cell ratio (p-lcr)", "platelet large cell ratio", "platelet to large cell ratio", "plcr", "p-lcr"],
        "unit": "%",
        "ref_range_male": "19.7 - 42.4",
        "min_val_male": 19.7,
        "max_val_male": 42.4,
        "ref_range_female": "19.7 - 42.4",
        "min_val_female": 19.7,
        "max_val_female": 42.4,
        "method": "Calculated"
    },
    {
        "category": "PLATELET COUNT & INDICES",
        "name": "PLATELETCRIT (PCT)",
        "aliases": ["plateletcrit (pct)", "pct"],
        "unit": "%",
        "ref_range_male": "0.19 - 0.39",
        "min_val_male": 0.19,
        "max_val_male": 0.39,
        "ref_range_female": "0.19 - 0.39",
        "min_val_female": 0.19,
        "max_val_female": 0.39,
        "method": "Calculated"
    }
]


def normalize_text(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r'[^a-zA-Z0-9\s\/\-]', ' ', str(text))
    return re.sub(r'\s+', ' ', clean).strip().lower()


def find_matching_test(raw_name: str) -> Optional[Dict[str, Any]]:
    cleaned_input = normalize_text(raw_name)
    if not cleaned_input:
        return None

    # Step 1: Exact matches first
    for entry in BLOOD_TESTS_REGISTRY:
        for alias in entry["aliases"]:
            if cleaned_input == normalize_text(alias):
                return entry

    # Step 2: Sort candidate aliases by descending length so specific terms (e.g. MCH, UIBC) match before substrings (e.g. Hemoglobin, Iron)
    candidates: List[Tuple[str, Dict[str, Any]]] = []
    for entry in BLOOD_TESTS_REGISTRY:
        for alias in entry["aliases"]:
            candidates.append((normalize_text(alias), entry))
    candidates.sort(key=lambda x: len(x[0]), reverse=True)

    for clean_alias, entry in candidates:
        if len(clean_alias) > 2 and re.search(r'\b' + re.escape(clean_alias) + r'\b', cleaned_input):
            return entry

    return None


def get_gender_specific_range(entry: Dict[str, Any], gender: str = "FEMALE") -> Tuple[str, Optional[float], Optional[float]]:
    """
    Returns (ref_range_str, min_val, max_val) tailored to Male or Female.
    """
    is_male = "M" in str(gender).upper() and "F" not in str(gender).upper()
    
    if is_male:
        return (
            entry.get("ref_range_male", entry.get("ref_range_female", "")),
            entry.get("min_val_male", entry.get("min_val_female")),
            entry.get("max_val_male", entry.get("max_val_female"))
        )
    else:
        return (
            entry.get("ref_range_female", entry.get("ref_range_male", "")),
            entry.get("min_val_female", entry.get("min_val_male")),
            entry.get("max_val_female", entry.get("max_val_male"))
        )


def determine_flag_gender(value_str: Any, min_val: Optional[float] = None, max_val: Optional[float] = None, is_phase_dependent: bool = False, ref_range_str: Optional[str] = None) -> str:
    if value_str is None:
        return "NORMAL"

    val_clean = str(value_str).strip()
    match_val = re.search(r'([0-9]+(?:\.[0-9]+)?)', val_clean)
    if not match_val:
        return "NORMAL"

    try:
        val = float(match_val.group(1))
    except ValueError:
        return "NORMAL"

    # If min_val or max_val is missing, attempt to extract bounds from ref_range_str
    if (min_val is None or max_val is None) and ref_range_str:
        range_clean = str(ref_range_str).replace("–", "-").replace("—", "-")
        m_range = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*-\s*([0-9]+(?:\.[0-9]+)?)', range_clean)
        if m_range:
            if min_val is None:
                min_val = float(m_range.group(1))
            if max_val is None:
                max_val = float(m_range.group(2))
        else:
            m_lt = re.search(r'<\s*([0-9]+(?:\.[0-9]+)?)', range_clean)
            if m_lt and max_val is None:
                max_val = float(m_lt.group(1))
            m_gt = re.search(r'>\s*([0-9]+(?:\.[0-9]+)?)', range_clean)
            if m_gt and min_val is None:
                min_val = float(m_gt.group(1))

    if max_val is not None and val > max_val:
        return "HIGH"
    if min_val is not None and val < min_val:
        return "LOW"

    return "NORMAL"


def ensure_test_flag(test: Dict[str, Any], gender: str = "FEMALE") -> Dict[str, Any]:
    """
    Guarantees that test has an accurate 'flag' ('HIGH', 'LOW', 'NORMAL')
    recalculated from its observed value and biological reference interval.
    """
    val = test.get("value")
    if not val or str(val).strip() in ["—", "-", "", "None"]:
        test["flag"] = "NORMAL"
        return test

    param_name = (test.get("parameter") or test.get("name") or "").upper()
    if "ANTI NUCLEAR ANTIBODIES" in param_name or param_name == "ANA" or "ANA (" in param_name:
        val_m = re.search(r'([0-9]+(?:\.[0-9]+)?)', str(val))
        if val_m:
            v_num = float(val_m.group(1))
            unit_str = str(test.get("unit", "")).upper()
            if "AU" in unit_str or v_num > 1.2 or "< 20" in str(test.get("ref_range", "")):
                test["unit"] = "AU/mL"
                test["ref_range"] = "< 20"
                test["max_val"] = 20.0
                test["min_val"] = None
                test["flag"] = "NORMAL" if v_num <= 20.0 else "HIGH"
                test["method"] = "C.M.I.A"
                return test

    ref_range = test.get("ref_range", "")
    min_val = test.get("min_val")
    max_val = test.get("max_val")
    is_phase = test.get("is_phase_dependent", False)

    flag = determine_flag_gender(val, min_val, max_val, is_phase, ref_range_str=ref_range)
    test["flag"] = flag
    return test


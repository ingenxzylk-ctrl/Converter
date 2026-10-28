import os
import re
from typing import Dict, Any, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

DEFAULT_SUPABASE_URL = "https://kpjxzhclrcpmnoiiyarr.supabase.co"
DEFAULT_SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtwanh6aGNscmNwbW5vaWl5YXJyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTA2NzAxNzQsImV4cCI6MjEwNjI0NjE3NH0.JscjB_kfpbrrKhI77luLrq1Hqg-YhRoll8ijGVEYmgg"

SUPABASE_URL = (os.getenv("SUPABASE_URL") or DEFAULT_SUPABASE_URL).strip('"\'')
SUPABASE_KEY = (os.getenv("SUPABASE_KEY") or DEFAULT_SUPABASE_KEY).strip('"\'')

_supabase_client: Optional[Client] = None

def get_supabase() -> Optional[Client]:
    """Initialize and return cached Supabase client singleton."""
    global _supabase_client
    if _supabase_client is None:
        url = (os.getenv("SUPABASE_URL") or DEFAULT_SUPABASE_URL).strip('"\'')
        key = (os.getenv("SUPABASE_KEY") or DEFAULT_SUPABASE_KEY).strip('"\'')
        if url and key:
            try:
                _supabase_client = create_client(url, key)
            except Exception as e:
                print(f"[Supabase Init Error] {e}")
    return _supabase_client


def save_report_to_supabase(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Saves parsed report metadata and test parameters into Supabase.
    PostgreSQL automatically partitions the row into patient_reports_male or
    patient_reports_female based on the gender column.
    """
    client = get_supabase()
    if not client:
        return {"status": "error", "message": "Supabase client not configured (check .env file)."}

    metadata = data.get("metadata", {})
    tests = data.get("tests", [])

    # 1. Determine Gender cleanly
    raw_gender = (metadata.get("gender") or "").upper().strip()
    test_type = (metadata.get("test_type") or "").upper()

    if "FEMALE" in raw_gender or "WOMEN" in test_type or "WOMAN" in test_type:
        gender = "FEMALE"
    elif "MALE" in raw_gender or "MEN" in test_type:
        gender = "MALE"
    else:
        gender = "FEMALE"

    # 2. Extract numeric age safely
    age_str = str(metadata.get("age_gender") or metadata.get("age") or "")
    age_digits = re.findall(r'\d+', age_str)
    age_val = int(age_digits[0]) if age_digits else None

    # 3. Format tests into clean JSON structures
    clean_test_params = []
    for t in tests:
        clean_test_params.append({
            "parameter": t.get("parameter") or t.get("name") or "",
            "value": str(t.get("value", "")),
            "unit": t.get("unit", ""),
            "ref_range": t.get("ref_range", ""),
            "flag": str(t.get("flag") or "NORMAL").upper(),
            "category": t.get("category", "")
        })

    # 4. Construct payload for master partitioned table with Indian Standard Time (IST)
    from datetime import datetime, timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist)
    time_ist_str = now_ist.strftime("%I:%M %p")  # e.g. "04:55 PM"
    date_time_ist_str = now_ist.strftime("%d %b %Y, %I:%M %p")  # e.g. "29 Sep 2026, 04:55 PM"

    payload = {
        "gender": gender,
        "patient_name": (metadata.get("patient_name") or "UNKNOWN").strip(),
        "phone": metadata.get("phone", ""),
        "age": age_val,
        "address": metadata.get("address", ""),
        "pincode": str(metadata.get("pincode") or ""),
        "collection_date": metadata.get("collection_date", ""),
        "report_date": metadata.get("report_date", ""),
        "package_name": metadata.get("test_type", ""),
        "sample_id": metadata.get("sample_id", ""),
        "lab_code": metadata.get("lab_code", ""),
        "clinical_notes": metadata.get("clinical_notes", ""),
        "test_parameters": clean_test_params,
        "time_ist": time_ist_str,
        "date_time_ist": date_time_ist_str
    }

    try:
        try:
            response = client.table("patient_reports").insert(payload).execute()
        except Exception as insert_err:
            err_msg = str(insert_err)
            # If the database table does not yet have the time_ist / date_time_ist column,
            # gracefully fall back to the base payload without failing the save operation
            if "time_ist" in err_msg or "date_time_ist" in err_msg or "PGRST204" in err_msg:
                fallback_payload = {k: v for k, v in payload.items() if k not in ("time_ist", "date_time_ist")}
                response = client.table("patient_reports").insert(fallback_payload).execute()
            else:
                raise insert_err

        saved_id = response.data[0]["id"] if response.data else None
        return {
            "status": "success",
            "id": saved_id,
            "gender": gender,
            "patient_name": payload["patient_name"],
            "saved_time_ist": time_ist_str,
            "saved_date_time_ist": date_time_ist_str,
            "total_tests": len(clean_test_params)
        }
    except Exception as e:
        print(f"[Supabase Insert Error] {e}")
        return {"status": "error", "message": str(e)}

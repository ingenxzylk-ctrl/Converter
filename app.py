"""
FastAPI Server for Lab Report Transformation & Re-branding Application.
100% Free, Local, No External APIs or LLMs.
"""

import os
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import re
import json
import shutil
from typing import Dict, Any, List

from pathlib import Path

from fastapi import FastAPI, File, UploadFile, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from parser import process_document

# Directory setup
BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
TEMPLATES_DIR = BASE_DIR / "templates"
SAMPLE_DATA_DIR = BASE_DIR / "sample_data"

STATIC_DIR = BASE_DIR / "static"

UPLOADS_DIR.mkdir(exist_ok=True)
SAMPLE_DATA_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

app = FastAPI(title="LabReport Transformer")

# Mount static and uploads directories
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the main split-screen application."""
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )


@app.post("/api/upload")
@app.post("/api/process")
async def upload_documents(files: List[UploadFile] = File(...)):
    """
    Receive one or multiple uploaded 3rd-party lab reports (PDFs and/or Images),
    parse them locally with RapidOCR / pdfplumber, and return merged extracted data.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    saved_paths = []
    for upload in files:
        if not upload.filename:
            continue
        filename = Path(upload.filename).name
        safe_filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
        target_path = UPLOADS_DIR / safe_filename
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(upload.file, buffer)
        saved_paths.append(str(target_path))

    if not saved_paths:
        raise HTTPException(status_code=400, detail="No valid files received")

    try:
        from parser import process_multiple_documents
        result = process_multiple_documents(saved_paths, str(UPLOADS_DIR))
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@app.get("/api/sample")
async def get_sample():
    """
    Return parsed data from the pre-generated sample third-party lab report.
    Allows instant zero-effort testing with real 53-analyte Thyrocare report.
    """
    thyrocare_pdf = SAMPLE_DATA_DIR / "thyrocare_third_party_report.pdf"
    if thyrocare_pdf.exists():
        target_path = thyrocare_pdf
    else:
        target_path = SAMPLE_DATA_DIR / "third_party_lab_report.pdf"
        if not target_path.exists():
            from sample_generator import generate_sample_pdf
            generate_sample_pdf(str(target_path))

    try:
        result = process_document(str(target_path), str(UPLOADS_DIR))
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sample error: {str(e)}")


@app.post("/preview", response_class=HTMLResponse)
async def preview_branded_report(request: Request, data: str = Form(...)):
    """
    Render the verified data inside your custom laboratory report template.
    Ready for printing or saving directly to PDF (A4 format).
    """
    try:
        payload = json.loads(data)
        clinic = payload.get("clinic", {})
        metadata = payload.get("metadata", {})
        tests = payload.get("tests", [])

        from blood_tests_db import ensure_test_flag
        gender = metadata.get("gender", "FEMALE")
        for t in tests:
            ensure_test_flag(t, gender=gender)

        flagged_tests = [t for t in tests if str(t.get("flag", "")).upper() in ["HIGH", "LOW"]]

        template_name = "zylk_template.html" if (TEMPLATES_DIR / "zylk_template.html").exists() else "branded_report.html"
        tmap = {}
        for t in tests:
            param = t.get("parameter") or t.get("name") or ""
            tmap[param] = t
            tmap[param.upper()] = t
            tmap[re.sub(r'[^a-zA-Z0-9]', '', param).upper()] = t

        return templates.TemplateResponse(
            request=request,
            name=template_name,
            context={
                "clinic": clinic,
                "metadata": metadata,
                "tests": tests,
                "flagged_tests": flagged_tests,
                "tmap": tmap
            }
        )
    except Exception as e:
        return HTMLResponse(content=f"<h3>Error rendering template: {str(e)}</h3>", status_code=500)


@app.post("/api/export-pdf")
async def export_branded_pdf(request: Request):
    """
    Generate an official print-perfect PDF using headless Playwright (Chromium).
    Enforces exact A4 margins, background graphics, and server-side rendering.
    Supports both JSON and form data payloads.
    """
    import io
    import traceback
    import logging
    from fastapi.responses import StreamingResponse
    from export_service import generate_zylk_report_bytes

    logger = logging.getLogger("uvicorn.error")

    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
        elif "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
            form = await request.form()
            raw_data = form.get("data", "{}")
            payload = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        else:
            body = await request.body()
            payload = json.loads(body.decode("utf-8"))

        metadata = payload.get("metadata", {})

        # Generate PDF using thread-safe Playwright runner
        pdf_bytes = await asyncio.to_thread(generate_zylk_report_bytes, payload)

        patient_name = metadata.get("patient_name", "patient").strip()
        safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', patient_name) or "report"

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="report_{safe_name}.pdf"'
            }
        )
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"PDF Generation Error:\n{tb}")
        err_msg = str(e).strip() or repr(e) or type(e).__name__
        raise HTTPException(status_code=500, detail=f"PDF Generation Error: {err_msg}")


@app.post("/api/export-word")
async def export_branded_word(request: Request):
    """
    Generate a branded .docx Word report from the current patient data.
    Mirrors the 3-tier structure of the PDF export.
    """
    import io
    import traceback
    import logging
    from fastapi.responses import StreamingResponse
    from word_export import generate_word_report_bytes

    logger = logging.getLogger("uvicorn.error")

    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
        else:
            body = await request.body()
            payload = json.loads(body.decode("utf-8"))

        metadata = payload.get("metadata", {})
        word_bytes = await asyncio.to_thread(generate_word_report_bytes, payload)

        patient_name = metadata.get("patient_name", "patient").strip()
        safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', patient_name) or "report"

        return StreamingResponse(
            io.BytesIO(word_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="report_{safe_name}.docx"'
            }
        )
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Word Generation Error:\n{tb}")
        err_msg = str(e).strip() or repr(e) or type(e).__name__
        raise HTTPException(status_code=500, detail=f"Word Generation Error: {err_msg}")



@app.post("/api/save-to-database")
async def save_to_database(request: Request):
    """
    Saves current patient report and tests into Supabase.
    PostgreSQL automatically partitions the row into male or female storage.
    """
    from db_service import save_report_to_supabase
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
        else:
            body = await request.body()
            payload = json.loads(body.decode("utf-8"))

        res = save_report_to_supabase(payload)
        if res.get("status") == "error":
            return JSONResponse(status_code=400, content=res)
        return JSONResponse(status_code=200, content=res)
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("LabReport Transformer is running!")
    print("Open your browser at: http://127.0.0.1:8000")
    print("="*60 + "\n")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)

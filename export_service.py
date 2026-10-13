"""
Export service for high-fidelity A4 PDF report generation using Playwright Chromium.
"""
from pathlib import Path
import re
import base64
from jinja2 import Environment, FileSystemLoader
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


def embed_static_images_as_base64(html_content: str, static_dir: Path) -> str:
    """Inline all local static images as base64 data URIs so Playwright renders them reliably."""
    def replacer(match):
        rel_path = match.group(1).lstrip("/")
        if rel_path.startswith("static/"):
            rel_path = rel_path[len("static/"):]
        file_path = static_dir / rel_path
        if file_path.exists() and file_path.is_file():
            mime = "image/png"
            if file_path.suffix.lower() in [".jpg", ".jpeg"]:
                mime = "image/jpeg"
            elif file_path.suffix.lower() == ".svg":
                mime = "image/svg+xml"
            with open(file_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            return f'src="data:{mime};base64,{b64}"'
        return match.group(0)

    return re.sub(r'src=["\'](/static/[^"\']+)["\']', replacer, html_content)


def render_zylk_report_html(patient_data: dict) -> str:
    """
    Renders patient_data using zylk_template.html (or branded_report.html)
    and inlines static images as base64 for self-contained, high-fidelity rendering.
    """
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template_name = "zylk_template.html" if (TEMPLATES_DIR / "zylk_template.html").exists() else "branded_report.html"
    template = env.get_template(template_name)

    clinic = patient_data.get("clinic", {})
    metadata = patient_data.get("metadata", {})
    tests = patient_data.get("tests", [])

    from blood_tests_db import ensure_test_flag
    gender = metadata.get("gender", "FEMALE")
    for t in tests:
        ensure_test_flag(t, gender=gender)

    flagged_tests = [t for t in tests if str(t.get("flag", "")).upper() in ["HIGH", "LOW"]]
    tmap = {}
    for t in tests:
        param = t.get("parameter") or t.get("name") or ""
        tmap[param] = t
        tmap[param.upper()] = t
        tmap[re.sub(r'[^a-zA-Z0-9]', '', param).upper()] = t

    html_content = template.render(
        clinic=clinic,
        metadata=metadata,
        tests=tests,
        flagged_tests=flagged_tests,
        tmap=tmap
    )

    return embed_static_images_as_base64(html_content, STATIC_DIR)


def generate_zylk_report(patient_data: dict, output_path: str) -> str:
    """
    Renders patient_data using zylk_template.html (or branded_report.html)
    and generates an official print-perfect A4 PDF with Playwright Chromium.
    Enforces zero-margin A4 layout and background graphics.
    """
    html_content_resolved = render_zylk_report_html(patient_data)

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    if sync_playwright is None:
        raise RuntimeError("Playwright is not installed in this environment. Use Word export or browser Print to PDF.")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--allow-file-access-from-files"]
        )
        page = browser.new_page()
        page.set_content(html_content_resolved, wait_until="load")
        page.pdf(
            path=str(out_file),
            format="A4",
            print_background=True,
            prefer_css_page_size=True,
            margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"}
        )
        browser.close()

    return str(out_file)


def generate_zylk_report_bytes(patient_data: dict) -> bytes:
    """
    Renders patient_data using zylk_template.html (or branded_report.html)
    and returns official print-perfect A4 PDF bytes directly.
    Returns None if Playwright is not installed or Chromium browser cannot launch.
    """
    if sync_playwright is None:
        return None

    html_content_resolved = render_zylk_report_html(patient_data)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--allow-file-access-from-files"]
            )
            page = browser.new_page()
            page.set_content(html_content_resolved, wait_until="load")
            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"}
            )
            browser.close()
        return pdf_bytes
    except Exception:
        # Browser launch failed or browser binary not downloaded in this environment
        return None



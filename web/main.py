from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BASE_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.pdf.generator import generate_protocol_pdf  # noqa: E402
from services.customers import customer_display_name, split_address
from src.database.customers import (
    add_customer as db_add_customer,
    delete_customer as db_delete_customer,
    load_customers,
    update_customer as db_update_customer,
)
from src.database.settings import get_setting, set_setting  # noqa: E402

APP_TITLE = "Protocol Manager"
WEB_EXPORTS_DIR = BASE_DIR / "exports" / "web"
LAST_PDF_PATH = WEB_EXPORTS_DIR / "last_protocol.pdf"

app = FastAPI(title=APP_TITLE)
app.mount("/static", StaticFiles(directory=BASE_DIR / "web" / "static"), name="static")
app.mount("/assets", StaticFiles(directory=BASE_DIR / "assets"), name="assets")

templates = Jinja2Templates(directory=BASE_DIR / "web" / "templates")

TRANSPORT_RECEIVERS = ["TNT", "DHL", "PPL", "GLS"]
DEFAULT_PROTOCOL_NUMBER = "0035/2026/PP/IK"
DEFAULT_SENDER = "Ivan Korec"


def _customers() -> list[dict[str, Any]]:
    return load_customers()


def _find_customer(display_name: str) -> dict[str, Any]:
    display_name = display_name.strip()
    for customer in _customers():
        if customer_display_name(customer) == display_name:
            return customer
        if customer.get("company", "") == display_name:
            return customer
    return {"company": display_name, "address": ""}


def _config() -> dict[str, Any]:
    return {
        "sender_name": get_setting("sender_name", DEFAULT_SENDER),
        "protocol_number": get_setting("protocol_number", DEFAULT_PROTOCOL_NUMBER),
    }


def _default_context(request: Request, **extra: Any) -> dict[str, Any]:
    config = _config()
    customers = _customers()
    recent_customers = customers[:4]
    customer_names = [customer_display_name(customer) for customer in customers]
    receiver_names = TRANSPORT_RECEIVERS + customer_names

    return {
        "request": request,
        "app_title": APP_TITLE,
        "customers": customers,
        "customer_names": customer_names,
        "recent_customers": recent_customers,
        "receiver_names": receiver_names,
        "today": datetime.now().strftime("%Y-%m-%d"),
        "today_display": datetime.now().strftime("%d.%m.%Y"),
        "sender_name": config.get("sender_name", DEFAULT_SENDER),
        "protocol_number": config.get("protocol_number", DEFAULT_PROTOCOL_NUMBER),
        **extra,
    }


def _build_items(item_types: list[str], item_values: list[str], item_counts: list[str]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []

    for item_type, value, count in zip(item_types, item_values, item_counts):
        item_type = item_type.strip()
        value = value.strip()
        count = count.strip()

        if not item_type and not value and not count:
            continue

        items.append({
            "type": item_type or "Položka",
            "value": value,
            "count": count or "1",
        })

    return items


def _date_to_pdf_format(date_value: str) -> str:
    if not date_value:
        return datetime.now().strftime("%d.%m.%Y")

    try:
        return datetime.strptime(date_value, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return date_value


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    customers = _customers()
    selected_customer = customers[0] if customers else {}

    return templates.TemplateResponse(
        "index.html",
        _default_context(
            request,
            selected_customer=selected_customer,
            selected_customer_name=customer_display_name(selected_customer) if selected_customer else "",
            selected_receiver="TNT",
            status="Připraveno ✔",
        ),
    )


@app.post("/settings")
def save_settings(
    sender_name: str = Form(...),
    protocol_number: str = Form(...),
) -> RedirectResponse:
    set_setting("sender_name", sender_name.strip() or DEFAULT_SENDER)
    set_setting("protocol_number", protocol_number.strip() or DEFAULT_PROTOCOL_NUMBER)

    return RedirectResponse(url="/?saved=1", status_code=303)


@app.get("/customers", response_class=HTMLResponse)
def customers_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "customers.html",
        _default_context(
            request,
            status="Správa zákazníků",
        ),
    )


@app.post("/customers/add")
def add_customer(
    company: str = Form(...),
    server: str = Form(""),
    address: str = Form(""),
) -> RedirectResponse:
    db_add_customer(company, server, address)
    return RedirectResponse(url="/customers", status_code=303)


@app.post("/customers/update/{customer_id}")
def update_customer(
    customer_id: int,
    company: str = Form(...),
    server: str = Form(""),
    address: str = Form(""),
) -> RedirectResponse:
    db_update_customer(customer_id, company, server, address)
    return RedirectResponse(url="/customers", status_code=303)


@app.post("/customers/delete/{customer_id}")
def delete_customer(customer_id: int) -> RedirectResponse:
    db_delete_customer(customer_id)
    return RedirectResponse(url="/customers", status_code=303)

@app.post("/preview", response_class=HTMLResponse)
def preview(
    request: Request,
    customer_name: str = Form(...),
    jira: str = Form(""),
    protocol_number: str = Form(...),
    protocol_date: str = Form(...),
    receiver: str = Form(...),
    sender_name: str = Form(...),
    item_type: list[str] = Form(default=[]),
    item_value: list[str] = Form(default=[]),
    item_count: list[str] = Form(default=[]),
) -> HTMLResponse:
    customer = _find_customer(customer_name)
    items = _build_items(item_type, item_value, item_count)

    data = {
        "protocol_number": protocol_number.strip(),
        "sender_name": sender_name.strip() or DEFAULT_SENDER,
        "customer_name": customer.get("company", customer_name).strip(),
        "customer_address": split_address(customer.get("address", "")),
        "jira": jira.strip(),
        "items": items,
        "date": _date_to_pdf_format(protocol_date),
        "receiver": receiver.strip() or "TNT",
    }

    WEB_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    generate_protocol_pdf(data, LAST_PDF_PATH)

    config = _config()
    config["sender_name"] = data["sender_name"]
    config["protocol_number"] = data["protocol_number"]
    save_config(config)

    return templates.TemplateResponse(
        "preview.html",
        _default_context(
            request,
            protocol=data,
            pdf_url=f"/pdf/latest?filename={quote(data['protocol_number'])}.pdf",
            status="PDF náhled vytvořen ✔",
        ),
    )


@app.get("/pdf/latest")
def latest_pdf(filename: str = "protocol.pdf") -> FileResponse:
    if not LAST_PDF_PATH.exists():
        return FileResponse(BASE_DIR / "assets" / "logo.png")

    return FileResponse(
        LAST_PDF_PATH,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from src.database.audit import (
    log_action,
    list_audit_log,
)

from fastapi import FastAPI, Form, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

BASE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BASE_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.pdf.generator import generate_protocol_pdf  # noqa: E402
from services.customers import customer_display_name, split_address
from src.database.customers import (
    add_customer as db_add_customer,
    delete_customer as db_delete_customer,
    get_customer_by_id,
    load_customers,
    update_customer as db_update_customer,
)

from src.database.database import connect  # noqa: E402

from src.database.settings import (
    claim_protocol_counter,
    get_setting,
    set_setting,
)  # noqa: E402

from src.database.protocols import (
    get_protocol_by_id,
    list_protocols,
    save_protocol,
)  # noqa: E402

from src.database.warehouse import (
    issue_protocol_items,
    add_warehouse_item,
    adjust_warehouse_quantity,
    archive_warehouse_item,
    delete_warehouse_item,
    get_warehouse_item,
    list_warehouse_items,
    list_warehouse_movements,
)  # noqa: E402

from src.database.users import (
    count_active_admins,
    create_user,
    delete_user,
    get_user_by_id,
    get_user_by_username,
    list_users,
    set_active,
    update_password,
    update_profile,
    update_role,
    update_theme,
)  # noqa: E402

from src.auth.security import hash_password, verify_password  # noqa: E402

APP_TITLE = "Protocol Manager"
WEB_EXPORTS_DIR = BASE_DIR / "exports" / "web"
LAST_PDF_PATH = WEB_EXPORTS_DIR / "last_protocol.pdf"
PROTOCOL_ARCHIVE_DIR = WEB_EXPORTS_DIR / "protocols"

app = FastAPI(title=APP_TITLE)

app.add_middleware(
    SessionMiddleware,
    secret_key="CHANGE_THIS_TO_A_LONG_RANDOM_SECRET_KEY",
)

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
        "protocol_number": get_setting(
            "protocol_number",
            DEFAULT_PROTOCOL_NUMBER,
        ),
        "theme": get_setting("theme", "light"),
    }


def _default_context(request: Request, **extra: Any) -> dict[str, Any]:
    config = _config()
    draft = request.session.get("draft_protocol", {})
    customers = _customers()
    recent_customers = customers[:4]
    customer_names = [customer_display_name(customer) for customer in customers]
    receiver_names = TRANSPORT_RECEIVERS + customer_names

    full_name = request.session.get("full_name", config.get("sender_name", DEFAULT_SENDER))
    saved_protocol_number = config.get("protocol_number", DEFAULT_PROTOCOL_NUMBER)
    counter = _protocol_counter(saved_protocol_number)
    protocol_number = _format_protocol_number(counter, full_name)

    return {
        "request": request,
        "app_title": APP_TITLE,
        "customers": customers,
        "customer_names": customer_names,
        "recent_customers": recent_customers,
        "receiver_names": receiver_names,
        "today": datetime.now().strftime("%Y-%m-%d"),
        "today_display": datetime.now().strftime("%d.%m.%Y"),
        "sender_name": full_name,
        "protocol_number": draft.get("protocol_number", protocol_number),
        "selected_customer_name": draft.get("customer_name", ""),
        "selected_receiver": draft.get("receiver", "TNT"),
        "selected_jira": draft.get("jira", ""),
        "selected_protocol_date": draft.get("protocol_date", datetime.now().strftime("%Y-%m-%d")),
        "selected_sender_name": full_name,
        "draft_items": draft.get("item_type", []),
        "draft_item_values": draft.get("item_value", []),
        "draft_item_counts": draft.get("item_count", []),
        "theme": request.session.get("theme", "light"),
        **extra,
    }

def _build_items(
    item_types: list[str],
    item_values: list[str],
    item_counts: list[str],
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []

    warehouse_item_names = {
        str(item["code"]).strip(): str(item["name"]).strip()
        for item in list_warehouse_items()
    }

    for item_type, value, count in zip(
        item_types,
        item_values,
        item_counts,
    ):
        item_type = item_type.strip()
        value = value.strip()
        count = count.strip()

        if not item_type and not value and not count:
            continue

        display_name = warehouse_item_names.get(
            item_type,
            item_type,
        )

        items.append({
            "type": display_name or "Položka",
            "value": value,
            "count": count or "1",
        })

    return items

def _is_logged_in(request: Request) -> bool:
    return bool(request.session.get("user_id"))


def _login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=303)


def _user_role(request: Request) -> str:
    return str(request.session.get("role", "user"))


def _role_redirect(request: Request) -> RedirectResponse:
    if _user_role(request) == "accounting":
        return RedirectResponse(url="/protocols", status_code=303)

    return RedirectResponse(url="/", status_code=303)


def _require_roles(
    request: Request,
    *allowed_roles: str,
) -> RedirectResponse | None:
    if not _is_logged_in(request):
        return _login_redirect()

    if _user_role(request) not in allowed_roles:
        return _role_redirect(request)

    return None

def _date_to_pdf_format(date_value: str) -> str:
    if not date_value:
        return datetime.now().strftime("%d.%m.%Y")

    try:
        return datetime.strptime(date_value, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return date_value

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
    "login.html",
    {
        "request": request,
        "app_title": APP_TITLE,
        "theme": "light",
        "error": "",
    },
)

@app.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user = get_user_by_username(username.strip())

    if user is None or not user["active"] or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
    "login.html",
    {
        "request": request,
        "app_title": APP_TITLE,
        "theme": "light",
        "error": "Neplatné uživatelské jméno nebo heslo.",
    },
    status_code=401,
)
    
    request.session.clear()

    request.session["user_id"] = user["id"]
    request.session["username"] = user["username"]
    request.session["full_name"] = user["full_name"]
    request.session["role"] = user["role"]
    request.session["theme"] = user.get("theme", "light")
    request.session["must_change_password"] = user.get("must_change_password", 0)

    if user.get("must_change_password", 0):
        return RedirectResponse(url="/account?force_password=1", status_code=303)

    if user["role"] == "accounting":
        return RedirectResponse(url="/protocols", status_code=303)

    return RedirectResponse(url="/", status_code=303)

@app.get("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@app.get("/account", response_class=HTMLResponse)
def account_page(request: Request) -> HTMLResponse:
    redirect = _require_roles(request, "admin", "user", "accounting")
    if redirect:
        return redirect

    return templates.TemplateResponse(
        "account.html",
        _default_context(
            request,
            force_password=request.query_params.get("force_password") == "1",
            error="",
            status="",
        ),
    )


@app.post("/account", response_class=HTMLResponse)
def account_save(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(...),
    role: str = Form(...),
    new_password: str = Form(""),
    confirm_password: str = Form(""),
) -> HTMLResponse:
    redirect = _require_roles(request, "admin", "user", "accounting")
    if redirect:
        return redirect

    username = username.strip()
    full_name = full_name.strip()

    was_force_password = (
        bool(request.session.get("must_change_password"))
        or request.query_params.get("force_password") == "1"
    )
    force_password = was_force_password

    if not username or not full_name:
        return templates.TemplateResponse(
            "account.html",
            _default_context(
                request,
                force_password=force_password,
                error="Login a jméno a příjmení jsou povinné.",
                status="",
            ),
            status_code=400,
        )

    if role not in {"user", "admin", "accounting"}:
        role = str(request.session.get("role", "user"))

    if request.session.get("role") != "admin":
        role = str(request.session.get("role", "user"))

    if new_password or confirm_password:
        if new_password != confirm_password:
            return templates.TemplateResponse(
                "account.html",
                _default_context(
                    request,
                    force_password=force_password,
                    error="Hesla se neshodují.",
                    status="",
                ),
                status_code=400,
            )

        if len(new_password) < 6:
            return templates.TemplateResponse(
                "account.html",
                _default_context(
                    request,
                    force_password=force_password,
                    error="Heslo musí mít alespoň 6 znaků.",
                    status="",
                ),
                status_code=400,
            )

        update_password(
            int(request.session["user_id"]),
            hash_password(new_password),
            must_change_password=0,
        )

        request.session["must_change_password"] = 0
        force_password = False

    update_profile(
        int(request.session["user_id"]),
        username,
        full_name,
        role,
    )

    request.session["username"] = username
    request.session["full_name"] = full_name
    request.session["role"] = role

    if was_force_password and new_password:
        if role == "accounting":
            return RedirectResponse(
                url="/protocols",
                status_code=303,
            )

        return RedirectResponse(
            url="/",
            status_code=303,
        )

    return templates.TemplateResponse(
        "account.html",
        _default_context(
            request,
            force_password=force_password,
            error="",
            status="Účet byl uložen.",
        ),
    )



@app.post("/reset-protocol-form")
def reset_protocol_form(request: Request) -> RedirectResponse:
    redirect = _require_roles(request, "admin", "user")
    if redirect:
        return redirect

    request.session.pop("draft_protocol", None)

    return RedirectResponse(
        url="/?reset=1",
        status_code=303,
    )

@app.get("/api/protocol-number")
def current_protocol_number(request: Request) -> dict[str, str]:
    redirect = _require_roles(request, "admin", "user")

    if redirect:
        return {"protocol_number": ""}

    full_name = request.session.get(
        "full_name",
        DEFAULT_SENDER,
    )

    saved_protocol_number = get_setting(
        "protocol_number",
        DEFAULT_PROTOCOL_NUMBER,
    )

    counter = _protocol_counter(saved_protocol_number)

    return {
        "protocol_number": _format_protocol_number(
            counter,
            full_name,
        ),
    }

@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    redirect = _require_roles(request, "admin", "user")
    if redirect:
        return redirect

    draft = request.session.get("draft_protocol", {})
    today = datetime.now().strftime("%Y-%m-%d")

    if draft.get("protocol_date") != today:
        draft["protocol_date"] = today
        request.session["draft_protocol"] = draft

    if request.query_params.get("reset") == "1":
        selected_customer_name = ""
    else:
        selected_customer_name = str(
            draft.get("customer_name", "")
        ).strip()

    selected_customer = (
        _find_customer(selected_customer_name)
        if selected_customer_name
        else {}
    )

    protocol_items = [
        item
        for item in list_warehouse_items()
        if bool(item["protocol_enabled"])
        and int(item["quantity"]) >= 1
    ]

    protocol_item_name_counts: dict[str, int] = {}

    for item in protocol_items:
        name_key = str(item["name"]).strip().casefold()
        protocol_item_name_counts[name_key] = (
            protocol_item_name_counts.get(name_key, 0) + 1
        )

    for item in protocol_items:
        name_key = str(item["name"]).strip().casefold()
        item["show_code"] = protocol_item_name_counts[name_key] > 1

    protocol_item_by_code = {
        str(item["code"]).strip().casefold(): item
        for item in protocol_items
    }

    return templates.TemplateResponse(
        "index.html",
        _default_context(
            request,
            selected_customer=selected_customer,
            selected_customer_name=selected_customer_name,
            protocol_items=protocol_items,
            protocol_item_by_code=protocol_item_by_code,
            status="Připraveno ✔",
        ),
    )

@app.post("/api/draft-protocol")
async def save_draft_protocol(request: Request) -> JSONResponse:
    redirect = _require_roles(request, "admin", "user")
    if redirect:
        return JSONResponse(
            {"success": False, "error": "Přístup odepřen."},
            status_code=403,
        )

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": "Neplatná data."},
            status_code=400,
        )

    item_types = payload.get("item_type", [])
    item_values = payload.get("item_value", [])
    item_counts = payload.get("item_count", [])

    if not isinstance(item_types, list):
        item_types = []

    if not isinstance(item_values, list):
        item_values = []

    if not isinstance(item_counts, list):
        item_counts = []

    current_draft = request.session.get("draft_protocol", {})

    request.session["draft_protocol"] = {
        "customer_name": str(
            payload.get("customer_name", "")
        ),
        "protocol_date": str(
            payload.get(
                "protocol_date",
                datetime.now().strftime("%Y-%m-%d"),
            )
        ),
        "jira": str(payload.get("jira", "")),
        "receiver": str(payload.get("receiver", "TNT")),
        "sender_name": str(
            request.session.get("full_name", DEFAULT_SENDER)
        ),
        "protocol_number": str(
            payload.get(
                "protocol_number",
                current_draft.get("protocol_number", ""),
            )
        ),
        "item_type": [
            str(value)
            for value in item_types
        ],
        "item_value": [
            str(value)
            for value in item_values
        ],
        "item_count": [
            str(value)
            for value in item_counts
        ],
    }

    return JSONResponse({"success": True})

@app.post("/settings")
def save_settings(
    request: Request,
    sender_name: str = Form(...),
    protocol_number: str = Form(...),
) -> RedirectResponse:
    redirect = _require_roles(request, "admin", "user")
    if redirect:
        return redirect
    set_setting("protocol_number", protocol_number.strip() or DEFAULT_PROTOCOL_NUMBER)

    return RedirectResponse(url="/?saved=1", status_code=303)

@app.post("/settings/protocol-number")
def save_protocol_number(
    request: Request,
    protocol_number: str = Form(...),
) -> RedirectResponse:
    redirect = _require_roles(request, "admin", "user")
    if redirect:
        return redirect

    clean_protocol_number = protocol_number.strip()

    if not clean_protocol_number:
        clean_protocol_number = DEFAULT_PROTOCOL_NUMBER

    set_setting("protocol_number", clean_protocol_number)
    
    draft = request.session.get("draft_protocol")

    if draft:
        draft["protocol_number"] = clean_protocol_number
        request.session["draft_protocol"] = draft

    return RedirectResponse(
        url="/?saved=protocol-number",
        status_code=303,
    )

@app.post("/theme")
def save_theme(
    request: Request,
    theme: str = Form(...),
    return_to: str = Form("/"),
) -> RedirectResponse:
    redirect = _require_roles(request, "admin", "user")
    if redirect:
        return redirect
    allowed_themes = {"light", "poison", "ocean", "purple", "casino", "carbon"}

    if theme not in allowed_themes:
        theme = "light"

    user_id = request.session.get("user_id")
    update_theme(user_id, theme)
    request.session["theme"] = theme

    return_to = return_to.strip()

    if not return_to.startswith("/") or return_to.startswith("//"):
        return_to = "/"

    separator = "&" if "?" in return_to else "?"

    return RedirectResponse(
        url=f"{return_to}{separator}theme_saved=1",
        status_code=303,
    )


@app.get("/l1-warehouse", response_class=HTMLResponse)
def l1_warehouse_page(request: Request) -> HTMLResponse:
    redirect = _require_roles(request, "admin", "user", "accounting")
    if redirect:
        return redirect

    status_messages = {
        "item-added": "Artikl byl přidán.",
        "quantity-updated": "Stav skladu byl upraven.",
        "item-archived": "Artikl byl archivován.",
        "item-deleted": "Artikl byl trvale odstraněn.",
    }

    return templates.TemplateResponse(
    "warehouse.html",
    _default_context(
        request,
        warehouse_items=list_warehouse_items(),
        status=status_messages.get(
            request.query_params.get("status", ""),
            "",
        ),
        error=request.query_params.get("error", ""),
    ),
)

@app.post("/l1-warehouse/items/add")
def l1_warehouse_add_item(
    request: Request,
    name: str = Form(...),
    code: str = Form(...),
    unit: str = Form("ks"),
    initial_quantity: int = Form(0),
    protocol_enabled: str | None = Form(None),
) -> RedirectResponse:
    redirect = _require_roles(request, "admin", "user", "accounting")
    if redirect:
        return redirect

    created_by = str(
        request.session.get("username")
        or request.session.get("full_name")
        or ""
    )

    success, message = add_warehouse_item(
        name=name,
        code=code,
        unit=unit,
        initial_quantity=initial_quantity,
        protocol_enabled=protocol_enabled == "1",
        created_by=created_by,
    )

    if not success:
        return RedirectResponse(
            url=f"/l1-warehouse?error={quote(message)}",
            status_code=303,
        )

    _audit(
        request,
        action="CREATE",
        entity="Sklad",
        description=f"Přidal skladový artikl '{name.strip()}'.",
)

    return RedirectResponse(
        url="/l1-warehouse?status=item-added",
        status_code=303,
    )


@app.post("/l1-warehouse/adjust")
def l1_warehouse_adjust(
    request: Request,
    item_id: int = Form(...),
    operation: str = Form(...),
    quantity: int = Form(...),
    note: str = Form(""),
) -> RedirectResponse:
    redirect = _require_roles(request, "admin", "user", "accounting")
    if redirect:
        return redirect

    created_by = str(
        request.session.get("username")
        or request.session.get("full_name")
        or ""
    )

    item = get_warehouse_item(item_id)
    item_name = (
        str(item["name"])
        if item
        else f"ID {item_id}"
    )

    success, message = adjust_warehouse_quantity(
        item_id=item_id,
        operation=operation,
        quantity=quantity,
        created_by=created_by,
        note=note,
    )

    if not success:
        return RedirectResponse(
            url=f"/l1-warehouse?error={quote(message)}",
            status_code=303,
        )

    operation_names = {
        "add": "Přidal množství",
        "remove": "Odebral množství",
        "set": "Nastavil skutečný stav",
    }

    operation_description = operation_names.get(
        operation,
        "Upravil stav",
    )

    _audit(
        request,
        action="UPDATE",
        entity="Sklad",
        entity_id=item_id,
        description=(
            f"{operation_description} artiklu "
            f"'{item_name}' – množství {quantity}."
        ),
    )

    return RedirectResponse(
        url="/l1-warehouse?status=quantity-updated",
        status_code=303,
    )


@app.post("/l1-warehouse/archive")
def archive_warehouse_item_route(
    request: Request,
    item_id: int = Form(...),
) -> RedirectResponse:
    redirect = _require_roles(
        request,
        "admin",
        "user",
        "accounting",
    )
    if redirect:
        return redirect

    item = get_warehouse_item(item_id)

    item_name = (
        str(item["name"])
        if item
        else f"ID {item_id}"
    )

    success, message = archive_warehouse_item(
        item_id=item_id,
    )

    if not success:
        return RedirectResponse(
            url=f"/l1-warehouse?error={quote(message)}",
            status_code=303,
        )

    _audit(
        request,
        action="DELETE",
        entity="Sklad",
        entity_id=item_id,
        description=f"Trvale odstranil skladový artikl '{item_name}'.",
    )

    return RedirectResponse(
        url="/l1-warehouse?status=item-archived",
        status_code=303,
    )


@app.post("/l1-warehouse/delete")
def delete_warehouse_item_route(
    request: Request,
    item_id: int = Form(...),
    force_delete: str | None = Form(None),
) -> RedirectResponse:
    redirect = _require_roles(
        request,
        "admin",
        "user",
        "accounting",
    )
    if redirect:
        return redirect

    item = get_warehouse_item(item_id)

    item_name = (
        str(item["name"])
        if item
        else f"ID {item_id}"
    )

    success, message = delete_warehouse_item(
        item_id=item_id,
        force=force_delete == "1",
    )

    if not success:
        return RedirectResponse(
            url=f"/l1-warehouse?error={quote(message)}",
            status_code=303,
        )

    _audit(
        request,
        action="DELETE",
        entity="Sklad",
        entity_id=item_id,
        description=f"Trvale odstranil skladový artikl '{item_name}'.",
    )

    return RedirectResponse(
        url="/l1-warehouse?status=item-deleted",
        status_code=303,
    )

@app.get("/l1-warehouse/history", response_class=HTMLResponse)
def l1_warehouse_history(request: Request) -> HTMLResponse:
    redirect = _require_roles(request, "admin", "user", "accounting")
    if redirect:
        return redirect

    return templates.TemplateResponse(
        "warehouse_history.html",
        _default_context(
            request,
            movements=list_warehouse_movements(),
        ),
    )

def _audit(
    request: Request,
    *,
    action: str,
    entity: str,
    description: str,
    entity_id: int | None = None,
) -> None:
    log_action(
        user_id=request.session.get("user_id"),
        username=str(
            request.session.get("username", "")
        ),
        action=action,
        entity_type=entity,
        entity_id=entity_id,
        description=description,
    )


@app.get("/customers", response_class=HTMLResponse)
def customers_page(request: Request) -> HTMLResponse:
    redirect = _require_roles(request, "admin","user")
    if redirect:
        return redirect

    return templates.TemplateResponse(
        "customers.html",
        _default_context(
            request,
            status="Správa zákazníků",
        ),
    )


@app.post("/customers/add")
def add_customer(
    request: Request,
    company: str = Form(...),
    server: str = Form(""),
    address: str = Form(""),
) -> RedirectResponse:
    redirect = _require_roles(request, "admin","user")
    if redirect:
        return redirect
    clean_company = company.strip()

    db_add_customer(
        clean_company,
        server.strip(),
        address.strip(),
    )

    _audit(
        request,
        action="CREATE",
        entity="Zákazník",
        description=(
            f"Přidal zákazníka '{clean_company}'."
        ),
    )

    return RedirectResponse(
        url="/customers",
        status_code=303,
    )


@app.post("/customers/update/{customer_id}")
def update_customer(
    request: Request,
    customer_id: int,
    company: str = Form(...),
    server: str = Form(""),
    address: str = Form(""),
) -> RedirectResponse:
    redirect = _require_roles(
        request,
        "admin",
        "user",
    )
    if redirect:
        return redirect

    clean_company = company.strip()

    db_update_customer(
        customer_id,
        clean_company,
        server.strip(),
        address.strip(),
    )

    _audit(
        request,
        action="UPDATE",
        entity="Zákazník",
        entity_id=customer_id,
        description=(
            f"Upravil zákazníka '{clean_company}'."
        ),
    )

    return RedirectResponse(
        url="/customers",
        status_code=303,
    )

@app.post("/customers/delete/{customer_id}")
def delete_customer(
    request: Request,
    customer_id: int,
) -> RedirectResponse:
    redirect = _require_roles(
        request,
        "admin",
        "user",
    )
    if redirect:
        return redirect

    customer = get_customer_by_id(customer_id)

    customer_name = (
        str(customer["company"])
        if customer
        else f"ID {customer_id}"
    )

    db_delete_customer(customer_id)

    _audit(
        request,
        action="DELETE",
        entity="Zákazník",
        entity_id=customer_id,
        description=(
            f"Smazal zákazníka '{customer_name}'."
        ),
    )

    return RedirectResponse(
        url="/customers",
        status_code=303,
    )

def _user_initials(full_name: str) -> str:
    parts = [part for part in full_name.strip().split() if part]

    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()

    if len(parts) == 1:
        return parts[0][:2].upper()

    return "XX"


def _format_protocol_number(counter: int, full_name: str) -> str:
    year = datetime.now().year
    initials = _user_initials(full_name)
    return f"{counter:04d}/{year}/PP/{initials}"


def _protocol_counter(protocol_number: str) -> int:
    first_part = protocol_number.split("/", 1)[0]

    try:
        return int(first_part)
    except ValueError:
        return 1

def _group_protocols_by_year(
    protocols: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}

    for protocol in protocols:
        protocol_date = protocol.get("protocol_date", "")
        protocol_number = protocol.get("protocol_number", "")

        year = ""

        number_parts = protocol_number.split("/")

        if len(number_parts) >= 2 and number_parts[1].isdigit():
            year = number_parts[1]

        if not year and len(protocol_date) >= 4:
            year = protocol_date[:4]

        if not year:
            year = "Neznámý rok"

        display_date = protocol_date

        try:
            display_date = datetime.strptime(
                protocol_date,
                "%Y-%m-%d",
            ).strftime("%d. %m. %Y")
        except ValueError:
            pass

        protocol["display_date"] = display_date
        grouped.setdefault(year, []).append(protocol)

    return [
        {
            "year": year,
            "protocols": grouped[year],
        }
        for year in sorted(grouped, reverse=True)
    ]


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
    redirect = _require_roles(request, "admin", "user")
    if redirect:
        return redirect

    authenticated_sender_name = str(
        request.session.get("full_name", DEFAULT_SENDER)
    ).strip()

    customer = _find_customer(customer_name)
    items = _build_items(item_type, item_value, item_count)

    request.session["draft_protocol"] = {
        "customer_name": customer_name,
        "protocol_date": protocol_date,
        "jira": jira,
        "receiver": receiver,
        "sender_name": authenticated_sender_name,
        "protocol_number": protocol_number,
        "item_type": item_type,
        "item_value": item_value,
        "item_count": item_count,
}

    data = {
        "protocol_number": protocol_number.strip(),
        "sender_name": authenticated_sender_name or DEFAULT_SENDER,
        "customer_name": customer.get("company", customer_name).strip(),
        "customer_address": split_address(customer.get("address", "")),
        "jira": jira.strip(),
        "items": items,
        "date": _date_to_pdf_format(protocol_date),
        "receiver": receiver.strip() or "TNT",
    }

    WEB_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    generate_protocol_pdf(data, LAST_PDF_PATH)

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


@app.get("/print/latest", response_class=HTMLResponse)
def print_latest_pdf(
    request: Request,
    protocol_number: str,
    overwrite: int = 0,
) -> HTMLResponse:
    redirect = _require_roles(request, "admin", "user")
    if redirect:
        return redirect

    draft = request.session.get("draft_protocol")

    if not draft:
        return RedirectResponse("/", status_code=303)

    requested_protocol_number = protocol_number.strip()

    if not requested_protocol_number:
        return HTMLResponse(
            "Číslo protokolu nesmí být prázdné.",
            status_code=400,
        )

    created_by = str(
        request.session.get("username", "")
    ).strip()

    full_name = str(
        request.session.get("full_name", DEFAULT_SENDER)
    ).strip()

    item_types = draft.get("item_type", [])
    item_values = draft.get("item_value", [])
    item_counts = draft.get("item_count", [])

    items = _build_items(
        item_types,
        item_values,
        item_counts,
    )

    items_search_parts: list[str] = []

    for item_type, item_value, item_count in zip(
        item_types,
        item_values,
        item_counts,
    ):
        parts = [
            str(item_type).strip(),
            str(item_value).strip(),
            str(item_count).strip(),
        ]

        items_search_parts.extend(
            part for part in parts if part
        )

    items_search = " ".join(items_search_parts)

    customer_name = str(
        draft.get("customer_name", "")
    ).strip()

    customer = _find_customer(customer_name)

    conn = connect()
    cursor = conn.cursor(dictionary=True)
    temporary_pdf_path: Path | None = None
    archived_pdf_path: Path | None = None

    try:
        conn.start_transaction()

        requested_parts = requested_protocol_number.split("/")

        if len(requested_parts) >= 3:
            requested_protocol_key = "/".join(
                requested_parts[:3]
            )
        else:
            requested_protocol_key = requested_protocol_number

        cursor.execute(
            """
            SELECT
                id,
                created_by
            FROM protocols
            WHERE protocol_key = %s
            """,
            (requested_protocol_key,),
        )

        existing_requested_protocol = cursor.fetchone()

        if existing_requested_protocol:
            existing_creator = (
                existing_requested_protocol["created_by"] or ""
            )

            if existing_creator == created_by:
                if not overwrite:
                    conn.rollback()

                    overwrite_url = (
                        "/print/latest?"
                        f"protocol_number="
                        f"{quote(requested_protocol_number, safe='')}"
                        "&overwrite=1"
                    )

                    return HTMLResponse(
                        f"""
                        <!doctype html>
                        <html lang="cs">
                        <head>
                            <meta charset="utf-8">
                            <title>Přepsat protokol?</title>
                        </head>
                        <body>
                            <script>
                                const confirmed = confirm(
                                    "Protokol s tímto číslem již existuje."
                                    + "\\n\\n"
                                    + "Chcete původní protokol přepsat?"
                                );

                                if (confirmed) {{
                                    window.location.replace(
                                        "{overwrite_url}"
                                    );
                                }} else if (window.opener) {{
                                    window.close();
                                }} else {{
                                    window.location.href = "/";
                                }}
                            </script>
                        </body>
                        </html>
                        """
                    )

                final_protocol_number = requested_protocol_number

            else:
                final_protocol_number = ""

        else:
            final_protocol_number = ""

        if not final_protocol_number:
            while True:
                claimed_counter = claim_protocol_counter(
                    conn,
                    DEFAULT_PROTOCOL_NUMBER,
                )

                candidate_protocol_number = _format_protocol_number(
                    claimed_counter,
                    full_name,
                )

                candidate_parts = candidate_protocol_number.split("/")

                if len(candidate_parts) >= 3:
                    candidate_protocol_key = "/".join(
                        candidate_parts[:3]
                    )
                else:
                    candidate_protocol_key = candidate_protocol_number

                candidate_exists = cursor.execute(
                    """
                    SELECT id
                    FROM protocols
                    WHERE protocol_key = %s
                    """,
                    (candidate_protocol_key,),
                )
                
                candidate_exists = cursor.fetchone()

                if candidate_exists is None:
                    final_protocol_number = candidate_protocol_number
                    break

        protocol_parts = final_protocol_number.split("/")

        try:
            protocol_year = protocol_parts[1]
        except IndexError:
            protocol_year = str(datetime.now().year)

        safe_filename = (
            final_protocol_number.replace("/", "-") + ".pdf"
        )

        archive_directory = (
            PROTOCOL_ARCHIVE_DIR / protocol_year
        )
        archive_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        archived_pdf_path = archive_directory / safe_filename

        temporary_pdf_path = archive_directory / (
            f".{safe_filename}.temporary"
        )

        pdf_data = {
            "protocol_number": final_protocol_number,
            "sender_name": str(
                draft.get("sender_name", full_name)
            ).strip() or DEFAULT_SENDER,
            "customer_name": customer.get(
                "company",
                customer_name,
            ).strip(),
            "customer_address": split_address(
                customer.get("address", "")
            ),
            "jira": str(
                draft.get("jira", "")
            ).strip(),
            "items": items,
            "date": _date_to_pdf_format(
                draft.get(
                    "protocol_date",
                    datetime.now().strftime("%Y-%m-%d"),
                )
            ),
            "receiver": str(
                draft.get("receiver", "TNT")
            ).strip() or "TNT",
        }

        generate_protocol_pdf(
            pdf_data,
            temporary_pdf_path,
        )

        save_result = save_protocol(
            protocol_number=final_protocol_number,
            protocol_date=draft.get(
                "protocol_date",
                datetime.now().strftime("%Y-%m-%d"),
            ),
            customer_name=customer_name,
            sender_name=pdf_data["sender_name"],
            receiver=pdf_data["receiver"],
            jira=pdf_data["jira"],
            items_search=items_search,
            pdf_path=archived_pdf_path,
            created_by=created_by,
            item_types=item_types,
            item_values=item_values,
            item_counts=item_counts,
            overwrite_existing=bool(overwrite),
            conn=conn,
        )

        if save_result == "conflict":
            conn.rollback()

            if temporary_pdf_path.exists():
                temporary_pdf_path.unlink()

            return HTMLResponse(
                """
                <!doctype html>
                <html lang="cs">
                <head>
                    <meta charset="utf-8">
                    <title>Duplicitní číslo protokolu</title>
                </head>
                <body>
                    <script>
                        alert(
                            "Protokol se nepodařilo uložit, protože "
                            + "stejné číslo právě použil jiný uživatel."
                        );

                        if (window.opener) {
                            window.close();
                        } else {
                            window.location.href = "/";
                        }
                    </script>
                </body>
                </html>
                """
            )

        if save_result == "overwrite_required":
            conn.rollback()

            if temporary_pdf_path.exists():
                temporary_pdf_path.unlink()

            return HTMLResponse(
                "Přepsání protokolu nebylo potvrzeno.",
                status_code=409,
            )

        if save_result not in {"created", "overwritten"}:
            conn.rollback()

            if temporary_pdf_path.exists():
                temporary_pdf_path.unlink()

            return HTMLResponse(
                "Protokol se nepodařilo uložit.",
                status_code=500,
            )

        warehouse_result, warehouse_message = issue_protocol_items(
            protocol_number=final_protocol_number,
            jira=pdf_data["jira"],
            created_by=created_by,
            item_types=item_types,
            item_counts=item_counts,
            conn=conn,
        )

        if not warehouse_result:
            conn.rollback()

            if temporary_pdf_path.exists():
                temporary_pdf_path.unlink()

            return HTMLResponse(
                warehouse_message,
                status_code=400,
            )

        protocol_number_parts = final_protocol_number.split("/")

        if len(protocol_number_parts) >= 3:
            final_protocol_key = "/".join(
                protocol_number_parts[:3]
            )
        else:
            final_protocol_key = final_protocol_number

        cursor.execute(
            """
            SELECT id
            FROM protocols
            WHERE protocol_key = %s
            """,
            (final_protocol_key,),
        )

        saved_protocol = cursor.fetchone()

        if saved_protocol is None:
            conn.rollback()

            if temporary_pdf_path.exists():
                temporary_pdf_path.unlink()

            return HTMLResponse(
                "Uložený protokol nebyl nalezen.",
                status_code=500,
            )

        protocol_id = int(saved_protocol["id"])

        if archived_pdf_path.exists():
            archived_pdf_path.unlink()

        temporary_pdf_path.replace(archived_pdf_path)
        temporary_pdf_path = None

        conn.commit()

        _audit(
            request,
            action=(
               "OVERWRITE"
               if save_result == "overwritten"
               else "CREATE"
           ),
           entity="Protokol",
           entity_id=protocol_id,
           description=(
               (
                    "Přepsal protokol "
                    if save_result == "overwritten"
                    else "Vytvořil protokol "
                )
                + final_protocol_number
       ),
)

    except Exception:
        conn.rollback()

        if (
            temporary_pdf_path is not None
            and temporary_pdf_path.exists()
        ):
            temporary_pdf_path.unlink()

        if (
            archived_pdf_path is not None
            and archived_pdf_path.exists()
        ):
            archived_pdf_path.unlink()

        raise

    finally:
        cursor.close()
        conn.close()

    next_saved_protocol_number = get_setting(
        "protocol_number",
        DEFAULT_PROTOCOL_NUMBER,
    )

    next_counter = _protocol_counter(
        next_saved_protocol_number
    )

    next_protocol_number = _format_protocol_number(
        next_counter,
        full_name,
    )

    draft["protocol_number"] = next_protocol_number
    request.session["draft_protocol"] = draft

    return templates.TemplateResponse(
        "print.html",
        {
            "request": request,
            "pdf_url": f"/protocols/{protocol_id}/pdf",
            "protocol_number": final_protocol_number,
        },
    )

@app.get("/protocols", response_class=HTMLResponse)
def protocols_page(request: Request) -> HTMLResponse:
    redirect = _require_roles(request, "admin", "user", "accounting")
    if redirect:
        return redirect

    protocol_groups = _group_protocols_by_year(list_protocols())
    total_protocols = sum(
        len(group["protocols"])
        for group in protocol_groups
    )

    return templates.TemplateResponse(
        "protocols.html",
        _default_context(
            request,
            theme=(
                "light"
                if request.session.get("role") == "accounting"
                else request.session.get("theme", "light")
            ),
            protocol_groups=protocol_groups,
            total_protocols=total_protocols,
            current_year=str(datetime.now().year),
        ),
    )


def archived_protocol_pdf(
    request: Request,
    protocol_id: int,
):
    if not _is_logged_in(request):
        return _login_redirect()

    protocol = get_protocol_by_id(protocol_id)

    if protocol is None:
        return RedirectResponse("/protocols", status_code=303)

    pdf_path = Path(protocol["pdf_path"]).resolve()
    archive_root = PROTOCOL_ARCHIVE_DIR.resolve()

    if not pdf_path.is_relative_to(archive_root):
        return RedirectResponse("/protocols", status_code=303)

    if not pdf_path.is_file():
        return RedirectResponse("/protocols", status_code=303)

    filename = protocol["protocol_number"].replace("/", "-") + ".pdf"

    return FileResponse(
    pdf_path,
    media_type="application/pdf",
    headers={
        "Content-Disposition": f'inline; filename="{filename}"',
    },
)

@app.get("/protocols/{protocol_id}/pdf")
def archived_protocol_pdf(
    request: Request,
    protocol_id: int,
):
    redirect = _require_roles(request, "admin", "user", "accounting")
    if redirect:
        return redirect

    protocol = get_protocol_by_id(protocol_id)

    if protocol is None:
        return RedirectResponse("/protocols", status_code=303)

    pdf_path = Path(protocol["pdf_path"]).resolve()
    archive_root = PROTOCOL_ARCHIVE_DIR.resolve()

    if not pdf_path.is_relative_to(archive_root):
        return RedirectResponse("/protocols", status_code=303)

    if not pdf_path.is_file():
        return RedirectResponse("/protocols", status_code=303)

    filename = protocol["protocol_number"].replace("/", "-") + ".pdf"

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )

@app.get("/protocols/{protocol_id}/open")
def open_protocol(
    request: Request,
    protocol_id: int,
) -> RedirectResponse:
    redirect = _require_roles(request, "admin", "user")
    if redirect:
        return redirect

    protocol = get_protocol_by_id(protocol_id)

    if protocol is None:
        return RedirectResponse(
            "/protocols",
            status_code=303,
        )

    _audit(
        request,
        action="REPRINT",
        entity="Protokol",
        entity_id=protocol_id,
        description=(
            f"Otevřel protokol "
            f"{protocol['protocol_number']} k přetisku."
        ),
   )

    request.session["draft_protocol"] = {
        "protocol_number": protocol["protocol_number"],
        "protocol_date": protocol["protocol_date"],
        "customer_name": protocol["customer_name"],
        "sender_name": protocol["sender_name"],
        "receiver": protocol["receiver"],
        "jira": protocol["jira"],
        "item_type": [
            item["item_type"]
            for item in protocol["items"]
        ],
        "item_value": [
            item["item_value"]
            for item in protocol["items"]
        ],
        "item_count": [
            item["item_count"]
            for item in protocol["items"]
        ],
    }

    return RedirectResponse(
        "/",
        status_code=303,
    )

@app.get("/protocols/{protocol_id}/download")
def download_archived_protocol(
    request: Request,
    protocol_id: int,
):
    redirect = _require_roles(request, "admin", "user", "accounting")
    if redirect:
        return redirect

    protocol = get_protocol_by_id(protocol_id)

    if protocol is None:
        return RedirectResponse("/protocols", status_code=303)

    pdf_path = Path(protocol["pdf_path"]).resolve()
    archive_root = PROTOCOL_ARCHIVE_DIR.resolve()

    if not pdf_path.is_relative_to(archive_root):
        return RedirectResponse("/protocols", status_code=303)

    if not pdf_path.is_file():
        return RedirectResponse("/protocols", status_code=303)

    filename = protocol["protocol_number"].replace("/", "-") + ".pdf"

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename,
    )

@app.get("/audit-log", response_class=HTMLResponse)
def audit_log_page(request: Request) -> HTMLResponse:
    redirect = _require_roles(request, "admin")
    if redirect:
        return redirect

    return templates.TemplateResponse(
        "audit_log.html",
        _default_context(
            request,
            audit_entries=list_audit_log(),
        ),
    )

@app.get("/users", response_class=HTMLResponse)
def users_page(request: Request):
    redirect = _require_roles(request, "admin")
    if redirect:
        return redirect

    return templates.TemplateResponse(
    "users.html",
    _default_context(
        request,
        users=list_users(),
    ),
)

@app.get("/users/new", response_class=HTMLResponse)
def user_new_page(request: Request):
    redirect = _require_roles(request, "admin")
    if redirect:
        return redirect

    return templates.TemplateResponse(
    "user_new.html",
    _default_context(
        request,
        error="",
        status="",
    ),
)


@app.post("/users/new", response_class=HTMLResponse)
def user_new_save(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(...),
    role: str = Form(...),
    active: str = Form("0"),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    redirect = _require_roles(request, "admin")
    if redirect:
        return redirect

    username = username.strip()
    full_name = full_name.strip()
    is_active = 1 if active == "1" else 0

    if not username or not full_name:
        return templates.TemplateResponse(
    "user_new.html",
    _default_context(
        request,
        error="Login a jméno jsou povinné.",
        status="",
    ),
    status_code=400,
)

    if role not in {"user", "admin", "accounting"}:
        role = "user"

    if new_password != confirm_password:
        return templates.TemplateResponse(
            "user_new.html",
            {
                "request": request,
                "app_title": APP_TITLE,
                "theme": request.session.get("theme", "light"),
                "error": "Hesla se neshodují.",
                "status": "",
            },
            status_code=400,
        )

    if len(new_password) < 6:
        return templates.TemplateResponse(
            "user_new.html",
            _default_context(
                request,
                error="Heslo musí mít alespoň 6 znaků.",
                status="",
            ),
            status_code=400,
        )

    if get_user_by_username(username) is not None:
        return templates.TemplateResponse(
            "user_new.html",
            _default_context(
                request,
                error="Uživatel s tímto loginem už existuje.",
                status="",
            ),
            status_code=400,
        )

    create_user(
        username=username,
        password_hash=hash_password(new_password),
        full_name=full_name,
        role=role,
        must_change_password=1,
        must_change_username=0,
    )

    _audit(
        request,
        action="CREATE",
        entity="Uživatel",
        description=(
            f"Vytvořil uživatele '{username}' "
            f"s rolí '{role}'."
        ),
   )

    return RedirectResponse("/users", status_code=303)

@app.get("/users/{user_id}", response_class=HTMLResponse)
def user_edit_page(request: Request, user_id: int):
    if not _is_logged_in(request):
        return _login_redirect()

    if request.session.get("role") != "admin":
        return RedirectResponse("/", status_code=303)

    user = get_user_by_id(user_id)

    if user is None:
        return RedirectResponse("/users", status_code=303)

    return templates.TemplateResponse(
    "user_edit.html",
    _default_context(
        request,
        user=user,
        error="",
        status="",
    ),
)


@app.post("/users/{user_id}", response_class=HTMLResponse)
def user_edit_save(
    request: Request,
    user_id: int,
    username: str = Form(...),
    full_name: str = Form(...),
    role: str = Form(...),
    active: str = Form("0"),
    new_password: str = Form(""),
    confirm_password: str = Form(""),
):
    if not _is_logged_in(request):
        return _login_redirect()

    if request.session.get("role") != "admin":
        return RedirectResponse("/", status_code=303)

    user = get_user_by_id(user_id)

    if user is None:
        return RedirectResponse("/users", status_code=303)

    username = username.strip()
    full_name = full_name.strip()
    is_active = 1 if active == "1" else 0

    if not username or not full_name:
        return templates.TemplateResponse(
            "user_edit.html",
            _default_context(
                request,
                user=user,
                error="Login a jméno jsou povinné.",
                status="",
            ),
            status_code=400,
        )

    if role not in {"user", "admin", "accounting"}:
        role = "user"

    if user["role"] == "admin" and role != "admin" and count_active_admins() <= 1:
        return templates.TemplateResponse(
            "user_edit.html",
            _default_context(
                request,
                user=user,
                error="Nelze odebrat práva poslednímu aktivnímu administrátorovi.",
                status="",
            ),
            status_code=400,
        )

    if user["role"] == "admin" and user["active"] and not is_active and count_active_admins() <= 1:
        return templates.TemplateResponse(
           "user_edit.html",
           _default_context(
               request,
               user=user,
               error="Nelze deaktivovat posledního aktivního administrátora.",
               status="",
            ),
            status_code=400,
        )

    if new_password != confirm_password:
        return templates.TemplateResponse(
           "user_edit.html",
           _default_context(
               request,
               user=user,
               error="Hesla se neshodují.",
               status="",
            ),
            status_code=400,
        )

        if len(new_password) < 6:
            return templates.TemplateResponse(
                "user_edit.html",
                _default_context(
                    request,
                    user=user,
                    error="Heslo musí mít alespoň 6 znaků.",
                    status="",
                ),
                status_code=400,
            )

        update_password(user_id, hash_password(new_password), must_change_password=1)

    update_profile(user_id, username, full_name, role)
    set_active(user_id, is_active)

    _audit(
        request,
        action="UPDATE",
        entity="Uživatel",
        entity_id=user_id,
        description=(
            f"Upravil uživatele '{username}', "
            f"roli '{role}' a stav "
            f"'{'aktivní' if is_active else 'neaktivní'}'."
        ),
    )

    if request.session.get("user_id") == user_id:
        request.session["username"] = username
        request.session["full_name"] = full_name
        request.session["role"] = role

    return RedirectResponse("/users", status_code=303)


@app.post("/users/{user_id}/delete")
def user_delete(request: Request, user_id: int):
    if not _is_logged_in(request):
        return _login_redirect()

    if request.session.get("role") != "admin":
        return RedirectResponse("/", status_code=303)

    user = get_user_by_id(user_id)

    if user is None:
        return RedirectResponse("/users", status_code=303)

    if user["role"] == "admin" and user["active"] and count_active_admins() <= 1:
        return RedirectResponse("/users", status_code=303)

    deleted_username = str(user["username"])

    delete_user(user_id)

    _audit(
        request,
        action="DELETE",
        entity="Uživatel",
        entity_id=user_id,
        description=(
            f"Smazal uživatele '{deleted_username}'."
        ),
    )

    return RedirectResponse("/users", status_code=303)
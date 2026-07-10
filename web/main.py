
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
    load_customers,
    update_customer as db_update_customer,
)
from src.database.settings import get_setting, set_setting  # noqa: E402

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
    "sender_name": get_setting("sender_name", DEFAULT_SENDER),
    "protocol_number": get_setting("protocol_number", DEFAULT_PROTOCOL_NUMBER),
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
        "selected_sender_name": draft.get("sender_name", full_name),
        "draft_items": draft.get("item_type", []),
        "draft_item_values": draft.get("item_value", []),
        "draft_item_counts": draft.get("item_count", []),
        "theme": request.session.get("theme", "light"),
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

def _is_logged_in(request: Request) -> bool:
    return bool(request.session.get("user_id"))


def _login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=303)

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

    request.session["user_id"] = user["id"]
    request.session["username"] = user["username"]
    request.session["full_name"] = user["full_name"]
    request.session["role"] = user["role"]
    request.session["theme"] = user.get("theme", "light")
    request.session["must_change_password"] = user.get("must_change_password", 0)

    if user.get("must_change_password", 0):
        return RedirectResponse(url="/account?force_password=1", status_code=303)

    return RedirectResponse(url="/", status_code=303)

@app.get("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@app.get("/account", response_class=HTMLResponse)
def account_page(request: Request):
    if not _is_logged_in(request):
        return _login_redirect()

    return templates.TemplateResponse(
        "account.html",
        {
            "request": request,
            "app_title": APP_TITLE,
            "theme": request.session.get("theme", "light"),
            "force_password": request.query_params.get("force_password") == "1",
            "error": "",
            "status": "",
        }
    )

@app.post("/account", response_class=HTMLResponse)
def account_save(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(...),
    role: str = Form(...),
    new_password: str = Form(""),
    confirm_password: str = Form(""),
):
    if not _is_logged_in(request):
        return _login_redirect()

    username = username.strip()
    full_name = full_name.strip()

    if not username or not full_name:
        return templates.TemplateResponse(
            "account.html",
            {
                "request": request,
                "app_title": APP_TITLE,
                "theme": request.session.get("theme", "light"),
                "error": "Login a jméno a příjmení jsou povinné.",
                "status": "",
            },
            status_code=400,
        )

    if role not in {"user", "admin"}:
        role = request.session.get("role", "user")

    if request.session.get("role") != "admin":
        role = request.session.get("role", "user")

    if new_password or confirm_password:
        if new_password != confirm_password:
            return templates.TemplateResponse(
                "account.html",
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
                "account.html",
                {
                    "request": request,
                    "app_title": APP_TITLE,
                    "theme": request.session.get("theme", "light"),
                    "error": "Heslo musí mít alespoň 6 znaků.",
                    "status": "",
                },
                status_code=400,
            )

        update_password(
            int(request.session["user_id"]),
            hash_password(new_password),
            must_change_password=0,
        )

    update_profile(
        int(request.session["user_id"]),
        username,
        full_name,
        role,
    )

    request.session["username"] = username
    request.session["full_name"] = full_name
    request.session["role"] = role

    return templates.TemplateResponse(
        "account.html",
        {
            "request": request,
            "app_title": APP_TITLE,
            "theme": request.session.get("theme", "light"),
            "error": "",
            "status": "Účet byl uložen.",
        },
    )

@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    if not _is_logged_in(request):
        return _login_redirect()
   
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

@app.post("/theme")
def save_theme(request: Request, theme: str = Form(...)) -> RedirectResponse:
    allowed_themes = {"light", "poison", "ocean", "purple", "casino", "carbon"}

    if theme not in allowed_themes:
        theme = "light"

    user_id = request.session.get("user_id")
    update_theme(user_id, theme)
    request.session["theme"] = theme

    return RedirectResponse(url="/?theme_saved=1", status_code=303)


@app.get("/customers", response_class=HTMLResponse)
def customers_page(request: Request) -> HTMLResponse:
    if not _is_logged_in(request):
        return _login_redirect()

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
    if not _is_logged_in(request):
        return _login_redirect()

    customer = _find_customer(customer_name)
    items = _build_items(item_type, item_value, item_count)

    request.session["draft_protocol"] = {
        "customer_name": customer_name,
        "protocol_date": protocol_date,
        "jira": jira,
        "receiver": receiver,
        "sender_name": sender_name,
        "protocol_number": protocol_number,
        "item_type": item_type,
        "item_value": item_value,
        "item_count": item_count,
}

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
def print_latest_pdf(request: Request, protocol_number: str) -> HTMLResponse:
    if not _is_logged_in(request):
        return _login_redirect()

    current_counter = _protocol_counter(protocol_number)
    next_counter = current_counter + 1

    full_name = request.session.get("full_name", DEFAULT_SENDER)
    next_protocol_number = _format_protocol_number(next_counter, full_name)

    set_setting("protocol_number", next_protocol_number)

    return templates.TemplateResponse(
        "print.html",
        {
            "request": request,
            "pdf_url": f"/pdf/latest?filename={quote(protocol_number)}.pdf",
        },
    )

@app.get("/users", response_class=HTMLResponse)
def users_page(request: Request):
    if not _is_logged_in(request):
        return _login_redirect()

    if request.session.get("role") != "admin":
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse(
        "users.html",
        {
            "request": request,
            "app_title": APP_TITLE,
            "theme": request.session.get("theme", "light"),
            "users": list_users(),
        },
    )

@app.get("/users/new", response_class=HTMLResponse)
def user_new_page(request: Request):
    if not _is_logged_in(request):
        return _login_redirect()

    if request.session.get("role") != "admin":
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse(
        "user_new.html",
        {
            "request": request,
            "app_title": APP_TITLE,
            "theme": request.session.get("theme", "light"),
            "error": "",
            "status": "",
        },
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
    if not _is_logged_in(request):
        return _login_redirect()

    if request.session.get("role") != "admin":
        return RedirectResponse("/", status_code=303)

    username = username.strip()
    full_name = full_name.strip()
    is_active = 1 if active == "1" else 0

    if not username or not full_name:
        return templates.TemplateResponse(
            "user_new.html",
            {
                "request": request,
                "app_title": APP_TITLE,
                "theme": request.session.get("theme", "light"),
                "error": "Login a jméno jsou povinné.",
                "status": "",
            },
            status_code=400,
        )

    if role not in {"user", "admin"}:
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
            {
                "request": request,
                "app_title": APP_TITLE,
                "theme": request.session.get("theme", "light"),
                "error": "Heslo musí mít alespoň 6 znaků.",
                "status": "",
            },
            status_code=400,
        )

    if get_user_by_username(username) is not None:
        return templates.TemplateResponse(
            "user_new.html",
            {
                "request": request,
                "app_title": APP_TITLE,
                "theme": request.session.get("theme", "light"),
                "error": "Uživatel s tímto loginem už existuje.",
                "status": "",
            },
            status_code=400,
        )

    create_user(
        username=username,
        password_hash=hash_password(new_password),
        full_name=full_name,
        role=role,
        must_change_password=0,
        must_change_username=0,
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
        {
            "request": request,
            "app_title": APP_TITLE,
            "theme": request.session.get("theme", "light"),
            "user": user,
            "error": "",
            "status": "",
        },
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
            {
                "request": request,
                "app_title": APP_TITLE,
                "theme": request.session.get("theme", "light"),
                "user": user,
                "error": "Login a jméno jsou povinné.",
                "status": "",
            },
            status_code=400,
        )

    if role not in {"user", "admin"}:
        role = "user"

    if user["role"] == "admin" and role != "admin" and count_active_admins() <= 1:
        return templates.TemplateResponse(
            "user_edit.html",
            {
                "request": request,
                "app_title": APP_TITLE,
                "theme": request.session.get("theme", "light"),
                "user": user,
                "error": "Nelze odebrat práva poslednímu aktivnímu administrátorovi.",
                "status": "",
            },
            status_code=400,
        )

    if user["role"] == "admin" and user["active"] and not is_active and count_active_admins() <= 1:
        return templates.TemplateResponse(
            "user_edit.html",
            {
                "request": request,
                "app_title": APP_TITLE,
                "theme": request.session.get("theme", "light"),
                "user": user,
                "error": "Nelze deaktivovat posledního aktivního administrátora.",
                "status": "",
            },
            status_code=400,
        )

    if new_password or confirm_password:
        if new_password != confirm_password:
            return templates.TemplateResponse(
                "user_edit.html",
                {
                    "request": request,
                    "app_title": APP_TITLE,
                    "theme": request.session.get("theme", "light"),
                    "user": user,
                    "error": "Hesla se neshodují.",
                    "status": "",
                },
                status_code=400,
            )

        if len(new_password) < 6:
            return templates.TemplateResponse(
                "user_edit.html",
                {
                    "request": request,
                    "app_title": APP_TITLE,
                    "theme": request.session.get("theme", "light"),
                    "user": user,
                    "error": "Heslo musí mít alespoň 6 znaků.",
                    "status": "",
                },
                status_code=400,
            )

        update_password(user_id, hash_password(new_password), must_change_password=1)

    update_profile(user_id, username, full_name, role)
    set_active(user_id, is_active)

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

    delete_user(user_id)

    return RedirectResponse("/users", status_code=303)
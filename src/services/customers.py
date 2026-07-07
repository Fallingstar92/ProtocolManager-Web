import json
import shutil
import sys
from pathlib import Path


def resource_path(relative_path: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path

    return Path(__file__).resolve().parents[2] / relative_path


def writable_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path.home() / ".local" / "share" / "ProtocolManager" / relative_path

    return Path(__file__).resolve().parents[2] / relative_path


CUSTOMERS_SOURCE_FILE = resource_path("data/customers.json")
CUSTOMERS_FILE = writable_path("data/customers.json")


def ensure_customers_file() -> None:
    if CUSTOMERS_FILE.exists():
        return

    CUSTOMERS_FILE.parent.mkdir(parents=True, exist_ok=True)

    if CUSTOMERS_SOURCE_FILE.exists():
        shutil.copy(CUSTOMERS_SOURCE_FILE, CUSTOMERS_FILE)


def load_customers() -> list[dict]:
    ensure_customers_file()

    if not CUSTOMERS_FILE.exists():
        return []

    with CUSTOMERS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_customers(customers: list[dict]) -> None:
    CUSTOMERS_FILE.parent.mkdir(parents=True, exist_ok=True)

    with CUSTOMERS_FILE.open("w", encoding="utf-8") as file:
        json.dump(customers, file, ensure_ascii=False, indent=4)


def customer_display_name(customer: dict) -> str:
    company = customer.get("company", "")
    server = customer.get("server", "")

    if server:
        return f"{company} ({server})"

    return company


def split_address(address: str) -> list[str]:
    if not address:
        return []

    return [line.strip() for line in address.split(",") if line.strip()]
from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


CML_CUSTOMERS_URL = (
    "http://cml/parser.php"
    "?dir=gdocs-csv"
    "&csv=customers_contact.csv"
    "&type=json"
)


def _fetch_cml_rows() -> list[dict[str, Any]]:
    request = Request(
        CML_CUSTOMERS_URL,
        headers={
            "User-Agent": "ProtocolManager/1.0",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=15) as response:
            raw_data = response.read().decode("utf-8-sig")
    except HTTPError as exc:
        raise RuntimeError(
            f"CML vrátilo HTTP chybu {exc.code}."
        ) from exc
    except URLError as exc:
        raise RuntimeError("CML není dostupné.") from exc
    except TimeoutError as exc:
        raise RuntimeError("CML neodpovědělo včas.") from exc

    try:
        rows = json.loads(raw_data)
    except json.JSONDecodeError as exc:
        raise RuntimeError("CML vrátilo neplatný JSON.") from exc

    if not isinstance(rows, list):
        raise RuntimeError("CML vrátilo neočekávaný formát dat.")

    return [
        row
        for row in rows
        if isinstance(row, dict)
    ]


def fetch_all_customers_from_cml() -> dict[str, dict[str, Any]]:
    customers_by_server: dict[str, dict[str, Any]] = {}

    for row in _fetch_cml_rows():
        server = str(row.get("", "")).strip().lower()
        company = str(row.get("company", "")).strip()
        address = str(
            row.get("company_headquarters", "")
        ).strip()

        if not server or not company:
            continue

        if not re.fullmatch(r"[a-z0-9_-]+", server):
            continue

        customers_by_server[server] = {
            "server": server,
            "company": company,
            "address": address,
        }

    return customers_by_server


def fetch_customer_from_cml(server: str) -> dict[str, Any]:
    server = server.strip().lower()

    if not server:
        raise ValueError("Server zákazníka není vyplněný.")

    if not re.fullmatch(r"[a-z0-9_-]+", server):
        raise ValueError(
            "Server zákazníka obsahuje neplatné znaky."
        )

    customers_by_server = fetch_all_customers_from_cml()
    customer = customers_by_server.get(server)

    if customer is None:
        raise LookupError(
            f"Server '{server}' nebyl v CML nalezen."
        )

    return customer


def load_cml_customers(
    servers: list[str],
) -> list[dict[str, Any]]:
    customers_by_server = fetch_all_customers_from_cml()
    customers: list[dict[str, Any]] = []
    seen_servers: set[str] = set()

    for raw_server in servers:
        server = str(raw_server).strip().lower()

        if not server or server in seen_servers:
            continue

        seen_servers.add(server)

        customer = customers_by_server.get(server)

        if customer is None:
            raise LookupError(
                f"Server '{server}' nebyl v CML nalezen."
            )

        customers.append(customer)

    return sorted(
        customers,
        key=lambda customer: (
            str(customer.get("company", "")).casefold(),
            str(customer.get("server", "")).casefold(),
        ),
    )


def load_customers() -> list[dict[str, Any]]:
    from src.database.customers import (
        load_customers as load_db_customers,
    )

    db_customers = load_db_customers()
    customers_by_server = fetch_all_customers_from_cml()
    customers: list[dict[str, Any]] = []

    for db_customer in db_customers:
        server = str(
            db_customer.get("server", "")
        ).strip().lower()

        if not server:
            continue

        cml_customer = customers_by_server.get(server)

        if cml_customer is None:
            raise LookupError(
                f"Server '{server}' z databáze nebyl v CML nalezen."
            )

        customers.append(
            {
                "id": db_customer["id"],
                "server": server,
                "company": cml_customer["company"],
                "address": cml_customer["address"],
            }
        )

    return sorted(
        customers,
        key=lambda customer: (
            str(customer.get("company", "")).casefold(),
            str(customer.get("server", "")).casefold(),
        ),
    )
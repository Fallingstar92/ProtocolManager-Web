from typing import Any

from src.database.database import connect


def load_customers() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, company, server, address
            FROM customers
            ORDER BY company COLLATE NOCASE, server COLLATE NOCASE
            """
        ).fetchall()

    return [dict(row) for row in rows]


def add_customer(company: str, server: str = "", address: str = "") -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO customers (company, server, address)
            VALUES (?, ?, ?)
            """,
            (company.strip(), server.strip(), address.strip()),
        )


def update_customer(customer_id: int, company: str, server: str = "", address: str = "") -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE customers
            SET company = ?, server = ?, address = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (company.strip(), server.strip(), address.strip(), customer_id),
        )


def delete_customer(customer_id: int) -> None:
    with connect() as conn:
        conn.execute(
            "DELETE FROM customers WHERE id = ?",
            (customer_id,),
        )
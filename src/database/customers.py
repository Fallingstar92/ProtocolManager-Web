from typing import Any

from src.database.database import connect


def load_customers() -> list[dict[str, Any]]:
    conn = connect()

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                id,
                company,
                server,
                address
            FROM customers
            ORDER BY company, server
            """
        )

        rows = cursor.fetchall()
        cursor.close()

        return rows

    finally:
        conn.close()


def get_customer_by_id(
    customer_id: int,
) -> dict[str, Any] | None:
    conn = connect()

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                id,
                company,
                server,
                address
            FROM customers
            WHERE id = %s
            """,
            (customer_id,),
        )

        row = cursor.fetchone()
        cursor.close()

        return row

    finally:
        conn.close()


def add_customer(
    company: str,
    server: str = "",
    address: str = "",
) -> None:
    conn = connect()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO customers (
                company,
                server,
                address
            )
            VALUES (%s, %s, %s)
            """,
            (
                company.strip(),
                server.strip(),
                address.strip(),
            ),
        )

        conn.commit()
        cursor.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def update_customer(
    customer_id: int,
    company: str,
    server: str = "",
    address: str = "",
) -> None:
    conn = connect()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE customers
            SET company = %s,
                server = %s,
                address = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (
                company.strip(),
                server.strip(),
                address.strip(),
                customer_id,
            ),
        )

        conn.commit()
        cursor.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def delete_customer(
    customer_id: int,
) -> None:
    conn = connect()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM customers
            WHERE id = %s
            """,
            (customer_id,),
        )

        conn.commit()
        cursor.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
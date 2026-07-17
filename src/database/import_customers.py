import json
from pathlib import Path

from src.database.database import connect


BASE_DIR = Path(__file__).resolve().parents[2]
CUSTOMERS_JSON = BASE_DIR / "data" / "customers.json"


def import_customers() -> None:
    with CUSTOMERS_JSON.open(
        "r",
        encoding="utf-8",
    ) as file:
        customers = json.load(file)

    conn = connect()

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM customers
            """
        )

        row = cursor.fetchone()
        existing_count = int(row["count"]) if row else 0

        if existing_count > 0:
            print(
                "Tabulka customers už obsahuje data. "
                "Import přeskočen."
            )
            return

        values = []

        for customer in customers:
            company = str(
                customer.get("company", "")
            ).strip()

            server = str(
                customer.get("server", "")
            ).strip()

            address = str(
                customer.get("address", "")
            ).strip()

            if not company:
                continue

            values.append(
                (
                    company,
                    server,
                    address,
                )
            )

        if values:
            cursor.executemany(
                """
                INSERT INTO customers (
                    company,
                    server,
                    address
                )
                VALUES (%s, %s, %s)
                """,
                values,
            )

        conn.commit()

        print(
            f"Importováno zákazníků: {len(values)}"
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    import_customers()
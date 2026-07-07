import json
from pathlib import Path

from src.database.database import connect


BASE_DIR = Path(__file__).resolve().parents[2]
CUSTOMERS_JSON = BASE_DIR / "data" / "customers.json"


def import_customers() -> None:
    with CUSTOMERS_JSON.open("r", encoding="utf-8") as file:
        customers = json.load(file)

    with connect() as conn:
        existing_count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]

        if existing_count > 0:
            print("Tabulka customers už obsahuje data. Import přeskočen.")
            return

        for customer in customers:
            conn.execute(
                """
                INSERT INTO customers (company, server, address)
                VALUES (?, ?, ?)
                """,
                (
                    customer.get("company", "").strip(),
                    customer.get("server", "").strip(),
                    customer.get("address", "").strip(),
                ),
            )

    print(f"Importováno zákazníků: {len(customers)}")


if __name__ == "__main__":
    import_customers()
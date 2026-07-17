import os
import sqlite3

import mysql.connector


SQLITE_PATH = "data/protocolmanager.db"

MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "protocolmanager",
    "password": os.environ["PROTOCOLMANAGER_DB_PASSWORD"],
    "database": "protocolmanager",
}


TABLES = [
    "customers",
    "settings",
    "users",
    "protocols",
    "warehouse_items",
    "protocol_items",
    "warehouse_movements",
    "audit_log",
]


def migrate_table(
    sqlite_conn: sqlite3.Connection,
    mysql_conn,
    table_name: str,
) -> None:
    rows = sqlite_conn.execute(
        f"SELECT * FROM {table_name}"
    ).fetchall()

    if not rows:
        print(f"{table_name}: 0 řádků")
        return

    columns = rows[0].keys()
    column_names = ", ".join(
        f"`{column}`"
        for column in columns
    )
    placeholders = ", ".join(
        ["%s"] * len(columns)
    )

    query = (
        f"INSERT INTO `{table_name}` "
        f"({column_names}) "
        f"VALUES ({placeholders})"
    )

    values = [
        tuple(row[column] for column in columns)
        for row in rows
    ]

    cursor = mysql_conn.cursor()
    cursor.executemany(query, values)
    cursor.close()

    print(f"{table_name}: {len(values)} řádků")


def main() -> None:
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    mysql_conn = mysql.connector.connect(
        **MYSQL_CONFIG
    )

    try:
        mysql_conn.start_transaction()

        cursor = mysql_conn.cursor()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        cursor.close()

        for table_name in TABLES:
            migrate_table(
                sqlite_conn,
                mysql_conn,
                table_name,
            )

        cursor = mysql_conn.cursor()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        cursor.close()

        mysql_conn.commit()
        print("Migrace dokončena.")

    except Exception:
        mysql_conn.rollback()
        raise

    finally:
        sqlite_conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    main()

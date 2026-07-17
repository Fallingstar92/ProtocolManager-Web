from pathlib import Path

from mysql.connector.errors import IntegrityError

from src.database.database import connect


def save_protocol(
    protocol_number: str,
    protocol_date: str,
    customer_name: str,
    sender_name: str,
    receiver: str,
    jira: str,
    items_search: str,
    pdf_path: Path,
    created_by: str,
    item_types: list[str] | None = None,
    item_values: list[str] | None = None,
    item_counts: list[str] | None = None,
    overwrite_existing: bool = False,
    conn=None,
) -> str:
    number_parts = protocol_number.strip().split("/")

    if len(number_parts) >= 3:
        protocol_key = "/".join(number_parts[:3])
    else:
        protocol_key = protocol_number.strip()

    clean_item_types = item_types or []
    clean_item_values = item_values or []
    clean_item_counts = item_counts or []

    own_connection = conn is None

    if own_connection:
        conn = connect()
        conn.start_transaction()

    cursor = conn.cursor(dictionary=True)

    def save_items(protocol_id: int) -> None:
        for position, (
            item_type,
            item_value,
            item_count,
        ) in enumerate(
            zip(
                clean_item_types,
                clean_item_values,
                clean_item_counts,
            )
        ):
            clean_type = str(item_type).strip()
            clean_value = str(item_value).strip()
            clean_count = str(item_count).strip()

            if (
                not clean_type
                and not clean_value
                and not clean_count
            ):
                continue

            cursor.execute(
                """
                INSERT INTO protocol_items (
                    protocol_id,
                    item_type,
                    item_value,
                    item_count,
                    position
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    protocol_id,
                    clean_type,
                    clean_value,
                    clean_count,
                    position,
                ),
            )

    try:
        cursor.execute(
            """
            SELECT
                id,
                protocol_number,
                created_by,
                pdf_path
            FROM protocols
            WHERE protocol_key = %s
            FOR UPDATE
            """,
            (protocol_key,),
        )

        existing = cursor.fetchone()

        if existing:
            existing_creator = str(
                existing.get("created_by") or ""
            )

            if existing_creator != created_by:
                if own_connection:
                    conn.rollback()

                return "conflict"

            if not overwrite_existing:
                if own_connection:
                    conn.rollback()

                return "overwrite_required"

            protocol_id = int(existing["id"])

            cursor.execute(
                """
                UPDATE protocols
                SET protocol_number = %s,
                    protocol_date = %s,
                    customer_name = %s,
                    sender_name = %s,
                    receiver = %s,
                    jira = %s,
                    items_search = %s,
                    pdf_path = %s,
                    created_by = %s
                WHERE id = %s
                """,
                (
                    protocol_number,
                    protocol_date,
                    customer_name,
                    sender_name,
                    receiver,
                    jira,
                    items_search,
                    str(pdf_path),
                    created_by,
                    protocol_id,
                ),
            )

            cursor.execute(
                """
                DELETE FROM protocol_items
                WHERE protocol_id = %s
                """,
                (protocol_id,),
            )

            save_items(protocol_id)

            if own_connection:
                conn.commit()

            return "overwritten"

        try:
            cursor.execute(
                """
                INSERT INTO protocols (
                    protocol_number,
                    protocol_key,
                    protocol_date,
                    customer_name,
                    sender_name,
                    receiver,
                    jira,
                    items_search,
                    pdf_path,
                    created_by
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    protocol_number,
                    protocol_key,
                    protocol_date,
                    customer_name,
                    sender_name,
                    receiver,
                    jira,
                    items_search,
                    str(pdf_path),
                    created_by,
                ),
            )

            protocol_id = int(cursor.lastrowid)

            save_items(protocol_id)

            if own_connection:
                conn.commit()

            return "created"

        except IntegrityError:
            if own_connection:
                conn.rollback()

            return "conflict"

    except Exception:
        if own_connection:
            conn.rollback()

        raise

    finally:
        cursor.close()

        if own_connection:
            conn.close()


def list_protocols() -> list[dict]:
    conn = connect()

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                id,
                protocol_number,
                protocol_date,
                customer_name,
                sender_name,
                receiver,
                jira,
                items_search,
                pdf_path,
                created_at
            FROM protocols
            ORDER BY protocol_date DESC,
                     created_at DESC
            """
        )

        rows = cursor.fetchall()
        cursor.close()

        return rows

    finally:
        conn.close()


def delete_protocol(
    protocol_id: int,
) -> dict | None:
    conn = connect()

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM protocols
            WHERE id = %s
            """,
            (protocol_id,),
        )

        row = cursor.fetchone()

        if row is None:
            cursor.close()
            return None

        cursor.execute(
            """
            DELETE FROM protocols
            WHERE id = %s
            """,
            (protocol_id,),
        )

        conn.commit()
        cursor.close()

        return row

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_protocol_by_id(
    protocol_id: int,
) -> dict | None:
    conn = connect()

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                id,
                protocol_number,
                protocol_date,
                customer_name,
                sender_name,
                receiver,
                jira,
                items_search,
                pdf_path,
                created_at
            FROM protocols
            WHERE id = %s
            """,
            (protocol_id,),
        )

        row = cursor.fetchone()

        if row is None:
            cursor.close()
            return None

        cursor.execute(
            """
            SELECT
                item_type,
                item_value,
                item_count,
                position
            FROM protocol_items
            WHERE protocol_id = %s
            ORDER BY position
            """,
            (protocol_id,),
        )

        item_rows = cursor.fetchall()
        cursor.close()

    finally:
        conn.close()

    protocol = dict(row)

    protocol["items"] = [
        {
            "item_type": item["item_type"],
            "item_value": item["item_value"],
            "item_count": item["item_count"],
        }
        for item in item_rows
    ]

    return protocol
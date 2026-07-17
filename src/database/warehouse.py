from __future__ import annotations

from typing import Any

from src.database.database import connect


def list_warehouse_items(
    *,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    where_clause = "" if include_inactive else "WHERE wi.active = 1"

    with connect() as conn:
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute(
                f"""
                SELECT
                    wi.id,
                    wi.code,
                    wi.name,
                    wi.unit,
                    wi.protocol_enabled,
                    wi.active,
                    wi.created_at,
                    COALESCE(SUM(wm.quantity_change), 0) AS quantity
                FROM warehouse_items wi
                LEFT JOIN warehouse_movements wm
                    ON wm.warehouse_item_id = wi.id
                {where_clause}
                GROUP BY
                    wi.id,
                    wi.code,
                    wi.name,
                    wi.unit,
                    wi.protocol_enabled,
                    wi.active,
                    wi.created_at
                ORDER BY wi.name
                """
            )

            return cursor.fetchall()

        finally:
            cursor.close()


def get_warehouse_item(item_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT
                    wi.id,
                    wi.code,
                    wi.name,
                    wi.unit,
                    wi.protocol_enabled,
                    wi.active,
                    wi.created_at,
                    COALESCE(SUM(wm.quantity_change), 0) AS quantity
                FROM warehouse_items wi
                LEFT JOIN warehouse_movements wm
                    ON wm.warehouse_item_id = wi.id
                WHERE wi.id = %s
                GROUP BY
                    wi.id,
                    wi.code,
                    wi.name,
                    wi.unit,
                    wi.protocol_enabled,
                    wi.active,
                    wi.created_at
                """,
                (item_id,),
            )

            return cursor.fetchone()

        finally:
            cursor.close()


def add_warehouse_item(
    *,
    name: str,
    code: str,
    unit: str = "ks",
    initial_quantity: int = 0,
    protocol_enabled: bool = True,
    created_by: str,
) -> tuple[bool, str]:
    clean_name = name.strip()
    clean_code = code.strip().upper()
    clean_unit = unit.strip() or "ks"

    if not clean_name:
        return False, "Název artiklu nesmí být prázdný."

    if not clean_code:
        return False, "Kód artiklu nesmí být prázdný."

    if initial_quantity < 0:
        return False, "Počáteční stav nesmí být záporný."

    with connect() as conn:
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT
                    id,
                    code,
                    name,
                    active
                FROM warehouse_items
                WHERE code = %s
                """,
                (clean_code,),
            )

            existing = cursor.fetchone()

            if existing:
                if bool(existing["active"]):
                    return (
                        False,
                        "Artikl se stejným názvem nebo kódem už existuje.",
                    )

                cursor.execute(
                    """
                    UPDATE warehouse_items
                    SET code = %s,
                        name = %s,
                        unit = %s,
                        protocol_enabled = %s,
                        active = 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (
                        clean_code,
                        clean_name,
                        clean_unit,
                        1 if protocol_enabled else 0,
                        existing["id"],
                    ),
                )

                if initial_quantity:
                    cursor.execute(
                        """
                        INSERT INTO warehouse_movements (
                            warehouse_item_id,
                            quantity_change,
                            movement_type,
                            source_type,
                            created_by,
                            note
                        )
                        VALUES (
                            %s,
                            %s,
                            'receipt',
                            'manual',
                            %s,
                            %s
                        )
                        """,
                        (
                            existing["id"],
                            initial_quantity,
                            created_by,
                            "Naskladnění při opětovné aktivaci artiklu",
                        ),
                    )

                conn.commit()
                return True, "Artikl byl znovu aktivován."

            cursor.execute(
                """
                INSERT INTO warehouse_items (
                    code,
                    name,
                    unit,
                    protocol_enabled,
                    active
                )
                VALUES (%s, %s, %s, %s, 1)
                """,
                (
                    clean_code,
                    clean_name,
                    clean_unit,
                    1 if protocol_enabled else 0,
                ),
            )

            item_id = int(cursor.lastrowid)

            if initial_quantity:
                cursor.execute(
                    """
                    INSERT INTO warehouse_movements (
                        warehouse_item_id,
                        quantity_change,
                        movement_type,
                        source_type,
                        created_by,
                        note
                    )
                    VALUES (
                        %s,
                        %s,
                        'initial_balance',
                        'manual',
                        %s,
                        %s
                    )
                    """,
                    (
                        item_id,
                        initial_quantity,
                        created_by,
                        "Počáteční stav artiklu",
                    ),
                )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()

    return True, "Artikl byl přidán."


def adjust_warehouse_quantity(
    *,
    item_id: int,
    operation: str,
    quantity: int,
    created_by: str,
    note: str = "",
) -> tuple[bool, str]:
    item = get_warehouse_item(item_id)

    if not item:
        return False, "Skladový artikl nebyl nalezen."

    current_quantity = int(item["quantity"])

    if quantity < 0:
        return False, "Množství nesmí být záporné."

    if operation == "add":
        if quantity == 0:
            return False, "Zadej množství větší než nula."

        quantity_change = quantity
        movement_type = "receipt"

    elif operation == "remove":
        if quantity == 0:
            return False, "Zadej množství větší než nula."

        if quantity > current_quantity:
            return (
                False,
                f"Nelze odebrat {quantity} {item['unit']}. "
                f"Na skladu je pouze {current_quantity} {item['unit']}.",
            )

        quantity_change = -quantity
        movement_type = "manual_issue"

    elif operation == "set":
        target_quantity = quantity

        if target_quantity < 0:
            return False, "Skutečný stav nesmí být záporný."

        quantity_change = target_quantity - current_quantity
        movement_type = "inventory"

        if quantity_change == 0:
            return False, "Zadaný stav je stejný jako současný stav."

    else:
        return False, "Neplatný typ skladové změny."

    with connect() as conn:
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT
                    COALESCE(SUM(quantity_change), 0) AS quantity
                FROM warehouse_movements
                WHERE warehouse_item_id = %s
                """,
                (item_id,),
            )

            row = cursor.fetchone()
            database_quantity = int(row["quantity"]) if row else 0

            if database_quantity + quantity_change < 0:
                return False, "Změna by způsobila záporný stav skladu."

            cursor.execute(
                """
                INSERT INTO warehouse_movements (
                    warehouse_item_id,
                    quantity_change,
                    movement_type,
                    source_type,
                    created_by,
                    note
                )
                VALUES (%s, %s, %s, 'manual', %s, %s)
                """,
                (
                    item_id,
                    quantity_change,
                    movement_type,
                    created_by,
                    note.strip(),
                ),
            )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()

    return True, "Stav skladu byl upraven."


def archive_warehouse_item(
    *,
    item_id: int,
) -> tuple[bool, str]:
    with connect() as conn:
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT
                    id,
                    active
                FROM warehouse_items
                WHERE id = %s
                """,
                (item_id,),
            )

            item = cursor.fetchone()

            if item is None:
                return False, "Skladový artikl nebyl nalezen."

            if not bool(item["active"]):
                return False, "Artikl už je archivovaný."

            cursor.execute(
                """
                UPDATE warehouse_items
                SET active = 0,
                    protocol_enabled = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (item_id,),
            )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()

    return True, "Artikl byl archivován."


def delete_warehouse_item(
    *,
    item_id: int,
    force: bool = False,
) -> tuple[bool, str]:
    with connect() as conn:
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT id
                FROM warehouse_items
                WHERE id = %s
                """,
                (item_id,),
            )

            item = cursor.fetchone()

            if item is None:
                return False, "Skladový artikl nebyl nalezen."

            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM warehouse_movements
                WHERE warehouse_item_id = %s
                """,
                (item_id,),
            )

            movement_count = cursor.fetchone()
            count = int(movement_count["count"]) if movement_count else 0

            if count > 0 and not force:
                return (
                    False,
                    "Artikl obsahuje historii pohybů. "
                    "Pro trvalé odstranění je potřeba smazání potvrdit.",
                )

            if count > 0:
                cursor.execute(
                    """
                    DELETE FROM warehouse_movements
                    WHERE warehouse_item_id = %s
                    """,
                    (item_id,),
                )

            cursor.execute(
                """
                DELETE FROM warehouse_items
                WHERE id = %s
                """,
                (item_id,),
            )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()

    return True, "Artikl byl trvale odstraněn."


def list_warehouse_movements(
    *,
    limit: int = 500,
) -> list[dict[str, Any]]:
    with connect() as conn:
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT
                    wm.id,
                    wm.quantity_change,
                    wm.movement_type,
                    wm.source_type,
                    wm.protocol_id,
                    wm.protocol_number,
                    wm.jira,
                    wm.created_by,
                    wm.note,
                    wm.created_at,
                    wi.name AS item_name,
                    wi.code AS item_code,
                    wi.unit AS item_unit,
                    (
                        SELECT COALESCE(
                            SUM(previous.quantity_change),
                            0
                        )
                        FROM warehouse_movements previous
                        WHERE previous.warehouse_item_id =
                            wm.warehouse_item_id
                          AND previous.id <= wm.id
                    ) AS quantity_after
                FROM warehouse_movements wm
                JOIN warehouse_items wi
                    ON wi.id = wm.warehouse_item_id
                ORDER BY wm.id DESC
                LIMIT %s
                """,
                (limit,),
            )

            return cursor.fetchall()

        finally:
            cursor.close()


def issue_protocol_items(
    *,
    protocol_number: str,
    jira: str,
    created_by: str,
    item_types: list[str],
    item_counts: list[str],
    conn=None,
) -> tuple[bool, str]:
    requested_quantities: dict[str, int] = {}

    for item_type, item_count in zip(item_types, item_counts):
        item_code = str(item_type).strip().upper()

        if not item_code:
            continue

        clean_item_count = str(item_count).strip()

        try:
            quantity = int(clean_item_count)

        except ValueError:
            return (
                False,
                f'Položka „{item_type}“ nemá platně zadaný počet.',
            )

        if quantity <= 0:
            return (
                False,
                f'Počet položky „{item_type}“ musí být větší než nula.',
            )

        requested_quantities[item_code] = (
            requested_quantities.get(item_code, 0) + quantity
        )

    if not requested_quantities:
        return True, "Protokol neobsahuje žádné skladové položky."

    clean_protocol_number = protocol_number.strip()

    if not clean_protocol_number:
        return False, "Číslo protokolu nesmí být prázdné."

    own_connection = conn is None

    if own_connection:
        conn = connect()

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id
            FROM warehouse_movements
            WHERE protocol_number = %s
              AND source_type = 'protocol'
              AND movement_type = 'protocol_issue'
            LIMIT 1
            """,
            (clean_protocol_number,),
        )

        existing_movement = cursor.fetchone()

        if existing_movement:
            return True, "Sklad byl pro tento protokol již odečten."

        warehouse_items: dict[str, dict[str, Any]] = {}

        for item_code, requested_quantity in requested_quantities.items():
            cursor.execute(
                """
                SELECT
                    wi.id,
                    wi.code,
                    wi.name,
                    wi.unit,
                    wi.active,
                    wi.protocol_enabled,
                    COALESCE(SUM(wm.quantity_change), 0) AS quantity
                FROM warehouse_items wi
                LEFT JOIN warehouse_movements wm
                    ON wm.warehouse_item_id = wi.id
                WHERE wi.code = %s
                GROUP BY
                    wi.id,
                    wi.code,
                    wi.name,
                    wi.unit,
                    wi.active,
                    wi.protocol_enabled
                """,
                (item_code,),
            )

            item = cursor.fetchone()

            if item is None:
                return (
                    False,
                    f"Skladový artikl s kódem {item_code} nebyl nalezen.",
                )

            if not item["active"] or not item["protocol_enabled"]:
                return (
                    False,
                    f'Skladový artikl „{item["name"]}“ není aktivní.',
                )

            current_quantity = int(item["quantity"])

            if requested_quantity > current_quantity:
                return (
                    False,
                    f'Nelze vydat {requested_quantity} {item["unit"]} '
                    f'artiklu „{item["name"]}“. '
                    f'Na skladu je pouze '
                    f'{current_quantity} {item["unit"]}.',
                )

            warehouse_items[item_code] = item

        for item_code, requested_quantity in requested_quantities.items():
            item = warehouse_items[item_code]

            cursor.execute(
                """
                INSERT INTO warehouse_movements (
                    warehouse_item_id,
                    quantity_change,
                    movement_type,
                    source_type,
                    protocol_number,
                    jira,
                    created_by,
                    note
                )
                VALUES (
                    %s,
                    %s,
                    'protocol_issue',
                    'protocol',
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    item["id"],
                    -requested_quantity,
                    clean_protocol_number,
                    jira.strip(),
                    created_by.strip(),
                    f"Výdej podle protokolu {clean_protocol_number}",
                ),
            )

        if own_connection:
            conn.commit()

        return True, "Skladové položky byly odečteny."

    except Exception:
        if own_connection:
            conn.rollback()

        raise

    finally:
        cursor.close()

        if own_connection:
            conn.close()
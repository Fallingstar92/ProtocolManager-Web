from __future__ import annotations

import json
from typing import Any

from src.database.database import connect


def log_action(
    *,
    user_id: int | None,
    username: str,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    description: str = "",
    details: dict[str, Any] | None = None,
) -> None:
    conn = connect()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO audit_log (
                user_id,
                username,
                action,
                entity_type,
                entity_id,
                description,
                details_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                username.strip(),
                action.strip(),
                entity_type.strip(),
                entity_id,
                description.strip(),
                json.dumps(
                    details or {},
                    ensure_ascii=False,
                ),
            ),
        )

        conn.commit()
        cursor.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def list_audit_log(
    *,
    limit: int = 500,
) -> list[dict[str, Any]]:
    conn = connect()

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                *
            FROM audit_log
            ORDER BY created_at DESC,
                     id DESC
            LIMIT %s
            """,
            (limit,),
        )

        rows = cursor.fetchall()
        cursor.close()

        return rows

    finally:
        conn.close()
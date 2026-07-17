from typing import Any

from src.database.database import connect


def get_user_by_username(
    username: str,
) -> dict[str, Any] | None:
    conn = connect()

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                theme,
                id,
                username,
                password_hash,
                full_name,
                role,
                active,
                created_at,
                must_change_password,
                must_change_username
            FROM users
            WHERE username = %s
            """,
            (username,),
        )

        row = cursor.fetchone()
        cursor.close()

        return row

    finally:
        conn.close()


def create_user(
    username: str,
    password_hash: str,
    full_name: str,
    role: str = "user",
    must_change_password: int = 1,
    must_change_username: int = 1,
) -> None:
    conn = connect()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO users (
                username,
                password_hash,
                full_name,
                role,
                must_change_password,
                must_change_username
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                username,
                password_hash,
                full_name,
                role,
                must_change_password,
                must_change_username,
            ),
        )

        conn.commit()
        cursor.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def list_users() -> list[dict[str, Any]]:
    conn = connect()

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                theme,
                id,
                username,
                full_name,
                role,
                active,
                created_at,
                must_change_password,
                must_change_username
            FROM users
            ORDER BY id
            """
        )

        rows = cursor.fetchall()
        cursor.close()

        return rows

    finally:
        conn.close()


def get_user_by_id(
    user_id: int,
) -> dict[str, Any] | None:
    conn = connect()

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                theme,
                id,
                username,
                password_hash,
                full_name,
                role,
                active,
                created_at,
                must_change_password,
                must_change_username
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )

        row = cursor.fetchone()
        cursor.close()

        return row

    finally:
        conn.close()


def update_password(
    user_id: int,
    password_hash: str,
    must_change_password: int = 1,
) -> None:
    conn = connect()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE users
            SET password_hash = %s,
                must_change_password = %s
            WHERE id = %s
            """,
            (
                password_hash,
                must_change_password,
                user_id,
            ),
        )

        conn.commit()
        cursor.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def update_username(
    user_id: int,
    username: str,
    must_change_username: int = 0,
) -> None:
    conn = connect()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE users
            SET username = %s,
                must_change_username = %s
            WHERE id = %s
            """,
            (
                username,
                must_change_username,
                user_id,
            ),
        )

        conn.commit()
        cursor.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def update_role(
    user_id: int,
    role: str,
) -> None:
    conn = connect()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE users
            SET role = %s
            WHERE id = %s
            """,
            (
                role,
                user_id,
            ),
        )

        conn.commit()
        cursor.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def set_active(
    user_id: int,
    active: int,
) -> None:
    conn = connect()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE users
            SET active = %s
            WHERE id = %s
            """,
            (
                active,
                user_id,
            ),
        )

        conn.commit()
        cursor.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def delete_user(
    user_id: int,
) -> None:
    conn = connect()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM users
            WHERE id = %s
            """,
            (user_id,),
        )

        conn.commit()
        cursor.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def count_active_admins() -> int:
    conn = connect()

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM users
            WHERE role = 'admin'
              AND active = 1
            """
        )

        row = cursor.fetchone()
        cursor.close()

        if row is None:
            return 0

        return int(row["count"])

    finally:
        conn.close()


def update_profile(
    user_id: int,
    username: str,
    full_name: str,
    role: str,
) -> None:
    conn = connect()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE users
            SET username = %s,
                full_name = %s,
                role = %s,
                must_change_username = 0
            WHERE id = %s
            """,
            (
                username,
                full_name,
                role,
                user_id,
            ),
        )

        conn.commit()
        cursor.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_theme(
    user_id: int,
) -> str:
    conn = connect()

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT theme
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )

        row = cursor.fetchone()
        cursor.close()

        if row is None:
            return "light"

        return str(row.get("theme") or "light")

    finally:
        conn.close()


def update_theme(
    user_id: int,
    theme: str,
) -> None:
    conn = connect()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE users
            SET theme = %s
            WHERE id = %s
            """,
            (
                theme,
                user_id,
            ),
        )

        conn.commit()
        cursor.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
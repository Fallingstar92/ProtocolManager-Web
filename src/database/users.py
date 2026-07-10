from typing import Any

from src.database.database import connect


def get_user_by_username(username: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
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
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def create_user(
    username: str,
    password_hash: str,
    full_name: str,
    role: str = "user",
    must_change_password: int = 1,
    must_change_username: int = 1,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO users (
                username,
                password_hash,
                full_name,
                role,
                must_change_password,
                must_change_username
            )
            VALUES (?, ?, ?, ?, ?, ?)
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

def list_users() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
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
        ).fetchall()

    return [dict(row) for row in rows]


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
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
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def update_password(user_id: int, password_hash: str, must_change_password: int = 1) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE users
            SET password_hash = ?,
                must_change_password = ?
            WHERE id = ?
            """,
            (password_hash, must_change_password, user_id),
        )


def update_username(user_id: int, username: str, must_change_username: int = 0) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE users
            SET username = ?,
                must_change_username = ?
            WHERE id = ?
            """,
            (username, must_change_username, user_id),
        )


def update_role(user_id: int, role: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE users
            SET role = ?
            WHERE id = ?
            """,
            (role, user_id),
        )


def set_active(user_id: int, active: int) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE users
            SET active = ?
            WHERE id = ?
            """,
            (active, user_id),
        )


def delete_user(user_id: int) -> None:
    with connect() as conn:
        conn.execute(
            """
            DELETE FROM users
            WHERE id = ?
            """,
            (user_id,),
        )


def count_active_admins() -> int:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM users
            WHERE role = 'admin'
              AND active = 1
            """
        ).fetchone()

    return int(row["count"])

def update_profile(user_id: int, username: str, full_name: str, role: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE users
            SET username = ?,
                full_name = ?,
                role = ?,
                must_change_username = 0
            WHERE id = ?
            """,
            (username, full_name, role, user_id),
        )

def get_theme(user_id: int) -> str:
    ...

def update_theme(user_id: int, theme: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE users
            SET theme = ?
            WHERE id = ?
            """,
            (theme, user_id),
        )
    ...
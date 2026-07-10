from src.auth.security import hash_password
from src.database.database import connect


def create_admin() -> None:
    username = input("Username: ").strip()
    full_name = input("Full name: ").strip()
    password = input("Password: ").strip()

    if not username or not full_name or not password:
        print("Username, full name and password are required.")
        return

    password_hash = hash_password(password)

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO users (username, password_hash, full_name, role)
            VALUES (?, ?, ?, ?)
            """,
            (username, password_hash, full_name, "admin"),
        )

    print("Admin user created.")


if __name__ == "__main__":
    create_admin()
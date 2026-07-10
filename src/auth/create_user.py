from src.auth.security import hash_password
from src.database.users import create_user, list_users, update_password


def print_users() -> None:
    users = list_users()

    if not users:
        print("No users found.")
        return

    print()
    print("ID  Username        Full name                 Role    Active")
    print("-" * 65)

    for user in users:
        active = "Yes" if user["active"] else "No"
        print(
            f"{user['id']:<3} "
            f"{user['username']:<15} "
            f"{user['full_name']:<25} "
            f"{user['role']:<7} "
            f"{active}"
        )

    print()


def create_new_user() -> None:
    username = input("Login name: ").strip()
    full_name = input("Whole name: ").strip()
    password = input("Temporary password: ").strip()
    role = input("Role (user/admin) [user]: ").strip().lower() or "user"

    if role not in {"user", "admin"}:
        print("Invalid role. Use 'user' or 'admin'.")
        return

    if not username or not full_name or not password:
        print("Login name, whole name and password are required.")
        return

    create_user(
        username=username,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
        must_change_password=1,
        must_change_username=1,
    )

    print("User created.")

def reset_password() -> None:
    print_users()

    user_id = input("User ID: ").strip()
    password = input("New temporary password: ").strip()

    if not user_id.isdigit() or not password:
        print("Valid user ID and password are required.")
        return

    update_password(
        user_id=int(user_id),
        password_hash=hash_password(password),
        must_change_password=1,
    )

    print("Password reset.")

def main() -> None:
    while True:
        print()
        print("===================================")
        print(" Protocol Manager - User Manager")
        print("===================================")
        print("1. Create user")
        print("2. List users")
        print("3. Reset password")
        print("0. Exit")

        choice = input("Select option: ").strip()

        if choice == "1":
            create_new_user()
        elif choice == "2":
            print_users()
        elif choice == "3":
            reset_password()
        elif choice == "0":
            break
        else:
            print("Invalid option.")


if __name__ == "__main__":
    main()
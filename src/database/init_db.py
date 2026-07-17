from src.database.database import connect


def init_db() -> None:
    conn = connect()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                company VARCHAR(255) NOT NULL,
                server VARCHAR(255) NOT NULL DEFAULT '',
                address TEXT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id)
            )
            ENGINE=InnoDB
            DEFAULT CHARSET=utf8mb4
            COLLATE=utf8mb4_czech_ci
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                `key` VARCHAR(191) NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (`key`)
            )
            ENGINE=InnoDB
            DEFAULT CHARSET=utf8mb4
            COLLATE=utf8mb4_czech_ci
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                username VARCHAR(191) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                role VARCHAR(32) NOT NULL DEFAULT 'user',
                active TINYINT(1) NOT NULL DEFAULT 1,
                must_change_password TINYINT(1) NOT NULL DEFAULT 0,
                must_change_username TINYINT(1) NOT NULL DEFAULT 0,
                theme VARCHAR(32) NOT NULL DEFAULT 'light',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uq_users_username (username)
            )
            ENGINE=InnoDB
            DEFAULT CHARSET=utf8mb4
            COLLATE=utf8mb4_czech_ci
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS protocols (
                id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                protocol_number VARCHAR(64) NOT NULL,
                protocol_key VARCHAR(64) NOT NULL,
                protocol_date VARCHAR(32) NOT NULL,
                customer_name VARCHAR(255) NOT NULL,
                sender_name VARCHAR(255) NOT NULL,
                receiver VARCHAR(255) NOT NULL DEFAULT '',
                jira VARCHAR(255) NOT NULL DEFAULT '',
                items_search TEXT NOT NULL,
                pdf_path TEXT NOT NULL,
                created_by VARCHAR(191) NOT NULL DEFAULT '',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uq_protocols_protocol_key (
                    protocol_key
                )
            )
            ENGINE=InnoDB
            DEFAULT CHARSET=utf8mb4
            COLLATE=utf8mb4_czech_ci
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS protocol_items (
                id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                protocol_id INT UNSIGNED NOT NULL,
                item_type VARCHAR(255) NOT NULL DEFAULT '',
                item_value TEXT NOT NULL,
                item_count VARCHAR(64) NOT NULL DEFAULT '',
                position INT NOT NULL DEFAULT 0,
                PRIMARY KEY (id),
                KEY idx_protocol_items_protocol (
                    protocol_id
                ),
                CONSTRAINT fk_protocol_items_protocol
                    FOREIGN KEY (protocol_id)
                    REFERENCES protocols(id)
                    ON DELETE CASCADE
            )
            ENGINE=InnoDB
            DEFAULT CHARSET=utf8mb4
            COLLATE=utf8mb4_czech_ci
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS warehouse_items (
                id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                code VARCHAR(191) NOT NULL,
                name VARCHAR(255) NOT NULL,
                unit VARCHAR(32) NOT NULL DEFAULT 'ks',
                protocol_enabled TINYINT(1) NOT NULL DEFAULT 1,
                active TINYINT(1) NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uq_warehouse_items_code (code),
                UNIQUE KEY uq_warehouse_items_name (name)
            )
            ENGINE=InnoDB
            DEFAULT CHARSET=utf8mb4
            COLLATE=utf8mb4_czech_ci
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS warehouse_movements (
                id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                warehouse_item_id INT UNSIGNED NOT NULL,
                quantity_change INT NOT NULL,
                movement_type VARCHAR(64) NOT NULL,
                source_type VARCHAR(64) NOT NULL DEFAULT 'manual',
                protocol_id INT UNSIGNED NULL,
                protocol_number VARCHAR(64) NOT NULL DEFAULT '',
                jira VARCHAR(255) NOT NULL DEFAULT '',
                created_by VARCHAR(191) NOT NULL DEFAULT '',
                note TEXT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                KEY idx_warehouse_movements_item (
                    warehouse_item_id
                ),
                KEY idx_warehouse_movements_protocol (
                    protocol_id
                ),
                CONSTRAINT fk_warehouse_movements_item
                    FOREIGN KEY (warehouse_item_id)
                    REFERENCES warehouse_items(id),
                CONSTRAINT fk_warehouse_movements_protocol
                    FOREIGN KEY (protocol_id)
                    REFERENCES protocols(id)
            )
            ENGINE=InnoDB
            DEFAULT CHARSET=utf8mb4
            COLLATE=utf8mb4_czech_ci
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_id INT UNSIGNED NULL,
                username VARCHAR(191) NOT NULL DEFAULT '',
                action VARCHAR(64) NOT NULL,
                entity_type VARCHAR(128) NOT NULL,
                entity_id INT NULL,
                description TEXT NOT NULL,
                details_json LONGTEXT NOT NULL,
                PRIMARY KEY (id),
                KEY idx_audit_log_created_at (
                    created_at
                ),
                KEY idx_audit_log_user_id (
                    user_id
                ),
                KEY idx_audit_log_entity (
                    entity_type,
                    entity_id
                ),
                CONSTRAINT fk_audit_log_user
                    FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE SET NULL
            )
            ENGINE=InnoDB
            DEFAULT CHARSET=utf8mb4
            COLLATE=utf8mb4_czech_ci
            """
        )

        default_warehouse_items = (
            (
                "FLASH64",
                "Flash",
                "ks",
            ),
            (
                "CHIP",
                "Chip",
                "ks",
            ),
            (
                "UNIVERSAL_FLASH",
                "Univerzální flash",
                "ks",
            ),
        )

        cursor.executemany(
            """
            INSERT IGNORE INTO warehouse_items (
                code,
                name,
                unit,
                protocol_enabled,
                active
            )
            VALUES (%s, %s, %s, 1, 1)
            """,
            default_warehouse_items,
        )

        conn.commit()
        cursor.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
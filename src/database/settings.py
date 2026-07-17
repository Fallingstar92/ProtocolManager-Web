from src.database.database import connect


def get_setting(
    key: str,
    default: str = "",
) -> str:
    conn = connect()

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT value
            FROM settings
            WHERE `key` = %s
            """,
            (key,),
        )

        row = cursor.fetchone()
        cursor.close()

        if row:
            return str(row["value"])

        return default

    finally:
        conn.close()


def set_setting(
    key: str,
    value: str,
) -> None:
    conn = connect()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO settings (`key`, value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                value = VALUES(value)
            """,
            (
                key,
                value,
            ),
        )

        conn.commit()
        cursor.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def claim_protocol_counter(
    conn,
    default_protocol_number: str,
) -> int:
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT value
        FROM settings
        WHERE `key` = 'protocol_number'
        FOR UPDATE
        """
    )

    row = cursor.fetchone()

    saved_protocol_number = (
        str(row["value"])
        if row
        else default_protocol_number
    )

    first_part = saved_protocol_number.split("/", 1)[0]

    try:
        claimed_counter = int(first_part)
    except ValueError:
        default_first_part = default_protocol_number.split("/", 1)[0]

        try:
            claimed_counter = int(default_first_part)
        except ValueError:
            claimed_counter = 1

    next_counter = claimed_counter + 1

    number_parts = saved_protocol_number.split("/")

    if len(number_parts) >= 4:
        next_protocol_number = "/".join(
            [
                f"{next_counter:04d}",
                *number_parts[1:],
            ]
        )
    else:
        next_protocol_number = str(next_counter)

    cursor.execute(
        """
        INSERT INTO settings (`key`, value)
        VALUES ('protocol_number', %s)
        ON DUPLICATE KEY UPDATE
            value = VALUES(value)
        """,
        (next_protocol_number,),
    )

    cursor.close()

    return claimed_counter
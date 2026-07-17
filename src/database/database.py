import os

import mysql.connector
from mysql.connector.connection import MySQLConnection


def connect() -> MySQLConnection:
    return mysql.connector.connect(
        host=os.getenv(
            "PROTOCOLMANAGER_DB_HOST",
            "127.0.0.1",
        ),
        port=int(
            os.getenv(
                "PROTOCOLMANAGER_DB_PORT",
                "3306",
            )
        ),
        user=os.getenv(
            "PROTOCOLMANAGER_DB_USER",
            "protocolmanager",
        ),
        password=os.environ[
            "PROTOCOLMANAGER_DB_PASSWORD"
        ],
        database=os.getenv(
            "PROTOCOLMANAGER_DB_NAME",
            "protocolmanager",
        ),
        charset="utf8mb4",
        collation="utf8mb4_czech_ci",
        autocommit=False,
    )
from pathlib import Path
import sqlite3

DATABASE = (
    Path(__file__).resolve()
    .parents[2]
    / "data"
    / "protocolmanager.db"
)


def connect():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn
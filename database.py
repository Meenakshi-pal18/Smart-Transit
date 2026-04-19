import hashlib
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

DB_PATH = Path(__file__).resolve().parent / "smarttransit.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS client_sync_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()


def hash_password(password: str, salt: Optional[str] = None) -> Dict[str, str]:
    salt = salt or os.urandom(16).hex()
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), 100_000
    ).hex()
    return {"salt": salt, "password_hash": password_hash}


def create_user(name: str, email: str, password: str) -> Dict[str, Any]:
    credentials = hash_password(password)
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO users (name, email, password_hash, salt)
            VALUES (?, ?, ?, ?)
            """,
            (name, email.lower().strip(), credentials["password_hash"], credentials["salt"]),
        )
        connection.commit()
        return {"id": cursor.lastrowid, "name": name, "email": email.lower().strip()}


def get_user_by_email(email: str) -> Optional[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()


def verify_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    row = get_user_by_email(email)
    if not row:
        return None

    hashed = hash_password(password, row["salt"])
    if hashed["password_hash"] != row["password_hash"]:
        return None

    return {"id": row["id"], "name": row["name"], "email": row["email"]}


def store_sync_event(event_type: str, payload: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO client_sync_events (event_type, payload)
            VALUES (?, ?)
            """,
            (event_type, payload),
        )
        connection.commit()

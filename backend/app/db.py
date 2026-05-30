import os
import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "app.db"
DB_PATH = Path(os.getenv("DATABASE_PATH", str(DEFAULT_DB_PATH)))


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_amazon_products_table(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(amazon_products)").fetchall()
    }
    if columns and "source_row_number" not in columns:
        connection.execute("DROP TABLE amazon_products")

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS amazon_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_row_number INTEGER NOT NULL UNIQUE,
            product_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            category TEXT,
            discounted_price_myr REAL,
            actual_price_myr REAL,
            discount_percentage REAL,
            rating REAL,
            rating_count INTEGER,
            about_product TEXT,
            user_id TEXT,
            user_name TEXT,
            review_id TEXT,
            review_title TEXT,
            review_content TEXT,
            img_link TEXT,
            product_link TEXT,
            imported_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def amazon_products_count() -> int:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM amazon_products"
        ).fetchone()
    return int(row["count"])


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        ensure_amazon_products_table(connection)
        connection.commit()

"""
Database Utilities for Order Persistence

Handles SQLite database operations for saving and retrieving orders.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "orders.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
ORDER_COLUMNS = ["order_id", "customer_name", "total_amount", "created_at", "status"]


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _get_orders_columns(cursor: sqlite3.Cursor) -> List[str]:
    """Get current column names from orders table."""
    cursor.execute("PRAGMA table_info(orders)")
    return [row["name"] for row in cursor.fetchall()]


def _rebuild_orders_table(cursor: sqlite3.Cursor, existing_columns: List[str]) -> None:
    """Rebuild orders table to match expected schema."""
    logger.info("Rebuilding orders table to match schema")
    cursor.execute("DROP TABLE IF EXISTS orders_new")
    cursor.execute(
        """
        CREATE TABLE orders_new (
            order_id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            total_amount REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'confirmed'
        )
        """
    )
    copy_columns = [col for col in ORDER_COLUMNS if col in existing_columns]
    if copy_columns:
        columns_csv = ", ".join(copy_columns)
        cursor.execute(
            f"INSERT INTO orders_new ({columns_csv}) SELECT {columns_csv} FROM orders"
        )
    cursor.execute("DROP TABLE orders")
    cursor.execute("ALTER TABLE orders_new RENAME TO orders")


def initialize_database() -> None:
    """Initialize database schema."""
    logger.info("Ensuring database schema exists at %s", DB_PATH)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='orders'"
        )
        if cursor.fetchone():
            existing_columns = _get_orders_columns(cursor)
            if set(existing_columns) != set(ORDER_COLUMNS):
                _rebuild_orders_table(cursor, existing_columns)
        else:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    customer_name TEXT NOT NULL,
                    total_amount REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'confirmed'
                )
                """
            )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                item_price REAL NOT NULL,
                addons TEXT,
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
            )
            """
        )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.exception("Error initializing database: %s", exc)
        raise
    finally:
        conn.close()


def save_order(
    order_id: str,
    customer_name: str,
    order_items: List[Dict],
    total_amount: float,
) -> bool:
    """Save an order to the database."""
    logger.info("Saving order %s (%s items)", order_id, len(order_items))
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO orders (order_id, customer_name, total_amount, status)
            VALUES (?, ?, ?, 'confirmed')
            """,
            (order_id, customer_name, total_amount),
        )

        for item in order_items:
            addons_json = json.dumps(item.get("addons", [])) if item.get("addons") else None
            cursor.execute(
                """
                INSERT INTO order_items (order_id, item_name, quantity, item_price, addons)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    item["item_name"],
                    item["quantity"],
                    item["item_price"],
                    addons_json,
                ),
            )

        conn.commit()
        return True
    except Exception as exc:
        logger.exception("Failed to save order %s: %s", order_id, exc)
        conn.rollback()
        return False
    finally:
        conn.close()


def get_order(order_id: str) -> Optional[Dict]:
    """Retrieve an order by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        order_row = cursor.fetchone()
        if not order_row:
            return None

        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        items_rows = cursor.fetchall()

        order = {
            "order_id": order_row["order_id"],
            "customer_name": order_row["customer_name"],
            "total_amount": order_row["total_amount"],
            "created_at": order_row["created_at"],
            "status": order_row["status"],
            "items": [],
        }

        for item_row in items_rows:
            order["items"].append(
                {
                    "item_name": item_row["item_name"],
                    "quantity": item_row["quantity"],
                    "item_price": item_row["item_price"],
                    "addons": json.loads(item_row["addons"]) if item_row["addons"] else [],
                }
            )

        return order
    finally:
        conn.close()


def get_all_orders(limit: int = 100) -> List[Dict]:
    """Get all orders with optional limit."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT order_id, customer_name, total_amount, created_at, status
            FROM orders
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        orders = []
        for row in cursor.fetchall():
            orders.append(
                {
                    "order_id": row["order_id"],
                    "customer_name": row["customer_name"],
                    "total_amount": row["total_amount"],
                    "created_at": row["created_at"],
                    "status": row["status"],
                }
            )
        return orders
    finally:
        conn.close()


# Ensure schema exists when the module loads
try:
    initialize_database()
except Exception:
    pass

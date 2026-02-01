"""
Database utilities for SQLite operations
"""
import sqlite3
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Database path
DB_DIR = Path(__file__).parent.parent.parent / "database"
DB_PATH = DB_DIR / "ecommerce.db"

def get_connection() -> sqlite3.Connection:
    """Get database connection with row factory"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    """Create database tables if they don't exist"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Products table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                stock_available INTEGER NOT NULL,
                rating REAL,
                review_count INTEGER,
                description TEXT,
                discount_percentage INTEGER,
                return_eligible BOOLEAN,
                delivery_time_days INTEGER
            )
        """)

        # Create indexes for products
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON products(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_price ON products(price)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rating ON products(rating)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_name ON products(product_name)")

        # Orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                order_status TEXT NOT NULL,
                order_date DATE NOT NULL,
                total_amount REAL,
                delivery_date DATE
            )
        """)

        # Create indexes for orders
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_customer ON orders(customer_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON orders(order_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_date ON orders(order_date)")

        # Order items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                item_price REAL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id)")

        # Product FAQs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_faqs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_faq_product ON product_faqs(product_id)")

        # Customers table (optional)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                customer_name TEXT
            )
        """)

        conn.commit()
        logger.info("Database initialized successfully")

    except Exception as e:
        conn.rollback()
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        conn.close()

# Initialize on module load
initialize_database()

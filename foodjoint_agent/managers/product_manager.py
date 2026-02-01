"""
Product Manager - Handle product catalog operations
"""
import sqlite3
import logging
from typing import List, Dict, Optional, Any
from functools import lru_cache
from foodjoint_agent.db.db_utils import get_connection
from foodjoint_agent.utils.fuzzy_search import fuzzy_match, get_best_match

logger = logging.getLogger(__name__)

class ProductManager:
    """Manage product catalog operations"""

    def search_by_name(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search products by name using fuzzy matching

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of product dictionaries
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Get all product names for fuzzy matching
            cursor.execute("SELECT product_id, product_name FROM products")
            all_products = cursor.fetchall()

            product_map = {row["product_name"]: row["product_id"] for row in all_products}
            product_names = list(product_map.keys())

            # Fuzzy match
            matches = fuzzy_match(query, product_names, threshold=0.6, limit=limit)

            if not matches:
                return []

            # Get full product details for matches
            results = []
            for product_name, score in matches:
                product_id = product_map[product_name]
                cursor.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
                row = cursor.fetchone()

                if row:
                    product = dict(row)
                    product["match_score"] = score
                    results.append(product)

            return results

        except Exception as e:
            logger.error(f"Error searching products by name: {e}")
            return []
        finally:
            conn.close()

    def search_by_category(
        self,
        category: str,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search products by category with optional price range

        Args:
            category: Product category
            price_min: Minimum price (optional)
            price_max: Maximum price (optional)
            limit: Maximum number of results

        Returns:
            List of product dictionaries
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Build query
            query = "SELECT * FROM products WHERE category = ?"
            params = [category]

            if price_min is not None:
                query += " AND price >= ?"
                params.append(price_min)

            if price_max is not None:
                query += " AND price <= ?"
                params.append(price_max)

            query += " ORDER BY rating DESC, review_count DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error searching products by category: {e}")
            return []
        finally:
            conn.close()

    def get_product_details(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific product

        Args:
            product_id: Product ID

        Returns:
            Product dictionary or None
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
            row = cursor.fetchone()

            return dict(row) if row else None

        except Exception as e:
            logger.error(f"Error getting product details: {e}")
            return None
        finally:
            conn.close()

    def check_availability(self, product_id: str) -> Dict[str, Any]:
        """
        Check stock availability for a product

        Args:
            product_id: Product ID

        Returns:
            Dictionary with availability info
        """
        product = self.get_product_details(product_id)

        if not product:
            return {"available": False, "message": "Product not found"}

        stock = product["stock_available"]

        if stock == 0:
            return {"available": False, "stock": 0, "message": "Out of stock"}
        elif stock < 5:
            return {"available": True, "stock": stock, "message": f"Low stock ({stock} units remaining)"}
        else:
            return {"available": True, "stock": stock, "message": "In stock"}

    def get_all_categories(self) -> List[str]:
        """Get list of all product categories"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT DISTINCT category FROM products ORDER BY category")
            rows = cursor.fetchall()
            return [row["category"] for row in rows]

        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return []
        finally:
            conn.close()

@lru_cache(maxsize=1)
def get_product_manager() -> ProductManager:
    """Get singleton ProductManager instance"""
    return ProductManager()

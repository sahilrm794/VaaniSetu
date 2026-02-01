"""
Order Manager - Handle order operations
"""
import sqlite3
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from foodjoint_agent.db.db_utils import get_connection
from foodjoint_agent.utils.validators import is_within_return_window, can_cancel_order, can_return_order

logger = logging.getLogger(__name__)

class OrderManager:
    """Manage order operations"""

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get order details with items

        Args:
            order_id: Order ID

        Returns:
            Order dictionary with items or None
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Get order
            cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
            order_row = cursor.fetchone()

            if not order_row:
                return None

            order = dict(order_row)

            # Get order items
            cursor.execute("""
                SELECT * FROM order_items WHERE order_id = ?
            """, (order_id,))
            items_rows = cursor.fetchall()

            order["items"] = [dict(row) for row in items_rows]

            return order

        except Exception as e:
            logger.error(f"Error getting order: {e}")
            return None
        finally:
            conn.close()

    def get_customer_orders(self, customer_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get recent orders for a customer

        Args:
            customer_id: Customer ID
            limit: Maximum number of orders

        Returns:
            List of order dictionaries
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM orders
                WHERE customer_id = ?
                ORDER BY order_date DESC
                LIMIT ?
            """, (customer_id, limit))

            rows = cursor.fetchall()
            orders = []

            for row in rows:
                order = dict(row)

                # Get items for each order
                cursor.execute("""
                    SELECT * FROM order_items WHERE order_id = ?
                """, (order["order_id"],))
                items_rows = cursor.fetchall()
                order["items"] = [dict(item_row) for item_row in items_rows]

                orders.append(order)

            return orders

        except Exception as e:
            logger.error(f"Error getting customer orders: {e}")
            return []
        finally:
            conn.close()

    def cancel_order(self, order_id: str, reason: str) -> Dict[str, Any]:
        """
        Cancel an order (policy-aware)

        Args:
            order_id: Order ID
            reason: Cancellation reason

        Returns:
            Result dictionary
        """
        order = self.get_order(order_id)

        if not order:
            return {
                "success": False,
                "message": f"Order {order_id} not found. Please verify the Order ID."
            }

        # Check if order can be cancelled
        if not can_cancel_order(order["order_status"]):
            return {
                "success": False,
                "message": f"Order {order_id} cannot be cancelled because it has status '{order['order_status']}'. Only orders with status 'Placed' can be cancelled. You can initiate a return once the order is delivered."
            }

        # Update order status
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE orders
                SET order_status = 'Cancelled'
                WHERE order_id = ?
            """, (order_id,))

            conn.commit()

            return {
                "success": True,
                "message": f"Order {order_id} has been successfully cancelled. Reason: {reason}"
            }

        except Exception as e:
            conn.rollback()
            logger.error(f"Error cancelling order: {e}")
            return {
                "success": False,
                "message": f"Failed to cancel order due to a system error. Please try again."
            }
        finally:
            conn.close()

    def initiate_return(self, order_id: str, product_id: str, reason: str) -> Dict[str, Any]:
        """
        Initiate return for a product (policy-aware)

        Args:
            order_id: Order ID
            product_id: Product ID to return
            reason: Return reason

        Returns:
            Result dictionary
        """
        order = self.get_order(order_id)

        if not order:
            return {
                "success": False,
                "message": f"Order {order_id} not found. Please verify the Order ID."
            }

        # Check order status
        if order["order_status"] != "Delivered":
            return {
                "success": False,
                "message": f"Returns can only be initiated for delivered orders. Your order status is '{order['order_status']}'."
            }

        # Check return window (30 days)
        if not is_within_return_window(order["order_date"], days=30):
            return {
                "success": False,
                "message": f"Return window has expired. Returns must be initiated within 30 days of delivery. Your order was placed on {order['order_date']}."
            }

        # Check if product is in order
        product_in_order = any(item["product_id"] == product_id for item in order["items"])

        if not product_in_order:
            return {
                "success": False,
                "message": f"Product {product_id} was not found in order {order_id}."
            }

        # Get product details to check return eligibility
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT return_eligible, product_name FROM products WHERE product_id = ?", (product_id,))
            product_row = cursor.fetchone()

            if not product_row:
                return {
                    "success": False,
                    "message": f"Product {product_id} not found in catalog."
                }

            product = dict(product_row)

            if not product["return_eligible"]:
                return {
                    "success": False,
                    "message": f"{product['product_name']} is not eligible for return due to hygiene and safety reasons (personal care, consumables, or digital downloads)."
                }

            # Return is eligible
            return {
                "success": True,
                "message": f"Return initiated for {product['product_name']} from order {order_id}. Reason: {reason}. You will receive a return authorization email with shipping instructions. Refund will be processed within 7-10 business days after the item passes inspection."
            }

        except Exception as e:
            logger.error(f"Error initiating return: {e}")
            return {
                "success": False,
                "message": "Failed to initiate return due to a system error. Please try again."
            }
        finally:
            conn.close()

def get_order_manager() -> OrderManager:
    """Get OrderManager instance"""
    return OrderManager()

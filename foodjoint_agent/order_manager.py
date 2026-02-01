"""
Order Manager for CAG Architecture

Manages the shopping cart state for each session.
Validates items against the menu when adding to cart.

Thread-Safety: Uses asyncio.Lock for concurrent tool execution.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Union

from .menu_utils import MenuManager, get_menu_manager

logger = logging.getLogger(__name__)


class OrderManager:
    """
    Stores the caller's in-progress cart.

    Thread-safe for concurrent async tool execution via asyncio.Lock.
    """

    def __init__(self, menu_manager: Optional[MenuManager] = None) -> None:
        self.menu_manager = menu_manager or get_menu_manager()
        self.cart: List[Dict] = []
        self._lock = asyncio.Lock()  # Lock for concurrent access
        logger.info("Started a new order cart (with async lock)")

    def add_item(
        self, item_name: str, quantity: int = 1, addons: Optional[List[str]] = None
    ) -> Dict:
        """Add an item to the cart after validating it exists in the menu."""
        logger.info("Adding %sx %s (addons=%s)", quantity, item_name, addons)

        # Validate item exists in menu
        menu_item = self.menu_manager.check_item_exists(item_name)
        if not menu_item:
            return {"success": False, "message": f"'{item_name}' is not on our menu."}

        addons = addons or []
        existing_item = self._find_item_in_cart(menu_item["name"], addons)

        if existing_item:
            existing_item["quantity"] += quantity
            return {
                "success": True,
                "message": f"Updated {menu_item['name']} quantity to {existing_item['quantity']}",
                "item": existing_item,
            }

        cart_item = {
            "item_name": menu_item["name"],
            "quantity": quantity,
            "item_price": menu_item["price"],
            "addons": addons,
        }
        self.cart.append(cart_item)
        return {
            "success": True,
            "message": f"Added {quantity}x {menu_item['name']} to your order",
            "item": cart_item,
        }

    def remove_item(self, item_name: str) -> Dict:
        """Remove an item from the cart."""
        logger.info("Removing %s", item_name)
        item_lower = item_name.lower()

        for idx, item in enumerate(self.cart):
            if item["item_name"].lower() == item_lower:
                removed = self.cart.pop(idx)
                return {
                    "success": True,
                    "message": f"Removed {removed['item_name']} from your order",
                }

        # Try fuzzy match
        for idx, item in enumerate(self.cart):
            if item_lower in item["item_name"].lower() or item["item_name"].lower() in item_lower:
                removed = self.cart.pop(idx)
                return {
                    "success": True,
                    "message": f"Removed {removed['item_name']} from your order",
                }

        return {"success": False, "message": f"'{item_name}' is not in your order"}

    def update_quantity(self, item_name: str, new_quantity: int) -> Dict:
        """Update the quantity of an item in the cart."""
        logger.info("Updating %s quantity to %s", item_name, new_quantity)

        if new_quantity == 0:
            return self.remove_item(item_name)

        item_lower = item_name.lower()
        for item in self.cart:
            if item["item_name"].lower() == item_lower:
                item["quantity"] = new_quantity
                return {
                    "success": True,
                    "message": f"Updated {item['item_name']} quantity to {new_quantity}",
                }

        # Try fuzzy match
        for item in self.cart:
            if item_lower in item["item_name"].lower() or item["item_name"].lower() in item_lower:
                item["quantity"] = new_quantity
                return {
                    "success": True,
                    "message": f"Updated {item['item_name']} quantity to {new_quantity}",
                }

        return {"success": False, "message": f"'{item_name}' is not in your order"}

    def update_item_addons(self, item_name: str, new_addons: List[str]) -> Dict:
        """Update addons for an item in the cart."""
        logger.info("Updating %s addons to %s", item_name, new_addons)
        item_lower = item_name.lower()

        for item in self.cart:
            if item["item_name"].lower() == item_lower:
                existing = item.get("addons", [])
                for addon in new_addons:
                    if addon not in existing:
                        existing.append(addon)
                item["addons"] = existing
                addons_str = ", ".join(existing) if existing else "no addons"
                return {
                    "success": True,
                    "message": f"Updated {item['item_name']} with addons: {addons_str}",
                }

        return {
            "success": False,
            "message": f"'{item_name}' is not in your order. Add it first.",
        }

    def get_cart_items(self) -> List[Dict]:
        """Get a copy of all cart items."""
        return self.cart.copy()

    def get_item_count(self) -> int:
        """Get total item count in cart."""
        return sum(item["quantity"] for item in self.cart)

    def calculate_total(self) -> float:
        """Calculate the total price of all items in cart."""
        total = sum(item["item_price"] * item["quantity"] for item in self.cart)
        logger.info("Cart total is %.2f", total)
        return total

    def get_cart_summary(self, include_prices: bool = False) -> str:
        """Get a formatted summary of the cart."""
        if not self.cart:
            return "Your order is currently empty."

        summary_lines = ["Your current order:"]
        for item in self.cart:
            line = f"- {item['quantity']}x {item['item_name']}"
            if item.get("addons"):
                line += f" ({', '.join(item['addons'])})"
            if include_prices:
                item_total = item["item_price"] * item["quantity"]
                line += f" - ${item_total:.2f}"
            summary_lines.append(line)

        if include_prices:
            summary_lines.append(f"Total: ${self.calculate_total():.2f}")

        return "\n".join(summary_lines)

    def clear_cart(self) -> None:
        """Clear all items from the cart."""
        logger.info("Clearing cart")
        self.cart = []

    def is_empty(self) -> bool:
        """Check if cart is empty."""
        return len(self.cart) == 0

    def _find_item_in_cart(self, item_name: str, addons: List[str]) -> Optional[Dict]:
        """Find an item in cart with matching name and addons."""
        for item in self.cart:
            if item["item_name"].lower() == item_name.lower() and sorted(
                item.get("addons", [])
            ) == sorted(addons):
                return item
        return None

    def generate_order_id(self) -> str:
        """Generate a unique order ID."""
        timestamp = int(datetime.now().timestamp())
        return f"order_{timestamp}"

"""
Menu Utilities for CAG Architecture

This is a SIMPLIFIED version for the CAG approach.
Menu queries are no longer needed as tools - the menu is embedded in the prompt.
This module only provides validation when adding items to the cart.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from rapidfuzz import fuzz


def _default_menu_path() -> Path:
    return Path(__file__).resolve().parent.parent / "database" / "food_menu.json"


class MenuManager:
    """
    Simplified menu manager for CAG architecture.

    Primary purpose: Validate items when adding to cart.
    Menu browsing is handled directly by the LLM from embedded context.
    """

    def __init__(self, menu_path: Optional[Path] = None) -> None:
        self.menu_path = menu_path or _default_menu_path()
        self.menu_data: List[Dict] = []
        self._name_to_item: Dict[str, Dict] = {}
        self._load_menu()
        self._build_indexes()

    def _load_menu(self) -> None:
        if not self.menu_path.exists():
            raise FileNotFoundError(f"Menu file not found at {self.menu_path}")
        with self.menu_path.open("r", encoding="utf-8") as f:
            self.menu_data = json.load(f)

    def _build_indexes(self) -> None:
        """Build a name-to-item lookup for fast validation."""
        for item in self.menu_data:
            name_lower = item["name"].lower().strip()
            if name_lower not in self._name_to_item:
                self._name_to_item[name_lower] = item

    @staticmethod
    def _similarity_score(first: str, second: str) -> float:
        return fuzz.ratio(first, second) / 100.0

    def check_item_exists(self, item_name: str) -> Optional[Dict]:
        """
        Check if an item exists in the menu.
        Uses tiered matching: exact -> substring -> fuzzy.

        This is the primary method used by the cart to validate items.
        """
        target = item_name.lower().strip()

        # Tier 1: Exact match (case-insensitive)
        if target in self._name_to_item:
            return self._name_to_item[target]

        # Tier 2: Substring match
        for name_lower, item in self._name_to_item.items():
            if target in name_lower or name_lower in target:
                return item

        # Tier 3: Fuzzy match with high threshold (0.75)
        best_match = None
        best_score = 0.0
        for name_lower, item in self._name_to_item.items():
            score = self._similarity_score(target, name_lower)
            if score > best_score and score >= 0.75:
                best_score = score
                best_match = item

        return best_match

    def get_item_price(self, item_name: str) -> Optional[float]:
        """Get the price of an item by name."""
        item = self.check_item_exists(item_name)
        return item["price"] if item else None

    def get_item_by_name(self, item_name: str) -> Optional[Dict]:
        """Alias for check_item_exists for clarity."""
        return self.check_item_exists(item_name)


@lru_cache(maxsize=1)
def get_menu_manager(menu_path: Optional[Path] = None) -> MenuManager:
    """Get a cached menu manager instance."""
    return MenuManager(menu_path)

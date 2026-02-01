"""
CAG (Cache-Augmented Generation) Menu Builder for FoodJoint

This module formats the entire menu JSON into a structured text format
that gets embedded directly into the system prompt. This eliminates
the need for tool calls to query the menu, reducing latency significantly.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List


def _default_menu_path() -> Path:
    return Path(__file__).resolve().parent.parent / "database" / "food_menu.json"


def load_menu(menu_path: Path | None = None) -> List[Dict]:
    """Load the raw menu JSON data."""
    path = menu_path or _default_menu_path()
    if not path.exists():
        raise FileNotFoundError(f"Menu file not found at {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _group_by_category(menu_data: List[Dict]) -> Dict[str, List[Dict]]:
    """Group menu items by category."""
    categories: Dict[str, List[Dict]] = {}
    for item in menu_data:
        cat = item.get("category", "other").lower()
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(item)
    return categories


def _format_item(item: Dict) -> str:
    """Format a single menu item as a string."""
    name = item.get("name", "Unknown")
    price = item.get("price", 0.0)
    # Only show price if it's greater than 0
    if price > 0:
        return f"- {name} - ${price:.2f}"
    return f"- {name} (free)"


def _deduplicate_items(items: List[Dict]) -> List[Dict]:
    """Remove duplicate items based on name (keep first occurrence)."""
    seen_names = set()
    unique_items = []
    for item in items:
        name = item.get("name", "").lower().strip()
        if name and name not in seen_names:
            seen_names.add(name)
            unique_items.append(item)
    return unique_items


@lru_cache(maxsize=1)
def build_menu_context(menu_path: Path | None = None) -> str:
    """
    Build a formatted menu string for embedding in the system prompt.

    This is the core of the CAG approach - the entire menu is formatted
    and cached so it can be injected into the context window at session start.

    Returns:
        A formatted string containing all menu items organized by category.
    """
    menu_data = load_menu(menu_path)
    categories = _group_by_category(menu_data)

    # Define category display order and descriptions
    category_order = [
        ("mains", "Burgers, Sandwiches & Hot Dogs"),
        ("sides", "Fries, Nuggets & Side Items"),
        ("drinks", "Beverages & Drinks"),
        ("desserts", "Desserts & Sweet Treats"),
        ("extras", "Sauces, Toppings & Extras"),
        ("kids", "Kids Meals"),
    ]

    lines = ["=" * 50]
    lines.append("COMPLETE FOODJOINT MENU")
    lines.append("=" * 50)
    lines.append("")
    lines.append("Use ONLY items from this menu. Never invent items or prices.")
    lines.append("")

    total_items = 0

    for cat_key, cat_title in category_order:
        if cat_key in categories:
            items = _deduplicate_items(categories[cat_key])
            # Sort items by name for consistency
            items.sort(key=lambda x: x.get("name", "").lower())

            lines.append(f"### {cat_title.upper()}")
            lines.append("-" * 40)

            for item in items:
                lines.append(_format_item(item))
                total_items += 1

            lines.append("")

    # Handle any uncategorized items
    handled_cats = {cat for cat, _ in category_order}
    for cat_key, items in categories.items():
        if cat_key not in handled_cats:
            items = _deduplicate_items(items)
            items.sort(key=lambda x: x.get("name", "").lower())

            lines.append(f"### {cat_key.upper()}")
            lines.append("-" * 40)

            for item in items:
                lines.append(_format_item(item))
                total_items += 1

            lines.append("")

    lines.append("=" * 50)
    lines.append(f"Total: {total_items} unique menu items")
    lines.append("=" * 50)

    return "\n".join(lines)


def get_menu_item_names(menu_path: Path | None = None) -> List[str]:
    """Get a list of all unique menu item names (for validation)."""
    menu_data = load_menu(menu_path)
    seen = set()
    names = []
    for item in menu_data:
        name = item.get("name", "").strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    return names


if __name__ == "__main__":
    # Test the menu builder
    menu_context = build_menu_context()
    print(menu_context)
    print(f"\nContext length: {len(menu_context)} characters")
    print(f"Estimated tokens: ~{len(menu_context) // 4} tokens")

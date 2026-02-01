"""
Input validation utilities
"""
from datetime import datetime, timedelta
from typing import Optional

def validate_product_id(product_id: str) -> bool:
    """Validate product ID format (P1001, P1002, etc.)"""
    if not product_id:
        return False
    return product_id.startswith("P") and len(product_id) >= 5

def validate_order_id(order_id: str) -> bool:
    """Validate order ID format (O0001, O0002, etc.)"""
    if not order_id:
        return False
    return order_id.startswith("O") and len(order_id) >= 5

def validate_customer_id(customer_id: str) -> bool:
    """Validate customer ID format (C0001, C0002, etc.)"""
    if not customer_id:
        return False
    return customer_id.startswith("C") and len(customer_id) >= 5

def validate_price_range(price_min: Optional[float], price_max: Optional[float]) -> bool:
    """Validate price range"""
    if price_min is not None and price_min < 0:
        return False
    if price_max is not None and price_max < 0:
        return False
    if price_min is not None and price_max is not None and price_min > price_max:
        return False
    return True

def is_within_return_window(order_date: str, days: int = 30) -> bool:
    """Check if order is within return window"""
    try:
        order_datetime = datetime.strptime(order_date, "%Y-%m-%d")
        today = datetime.now()
        days_since_order = (today - order_datetime).days
        return days_since_order <= days
    except:
        return False

def can_cancel_order(order_status: str) -> bool:
    """Check if order can be cancelled based on status"""
    cancellable_statuses = ["Placed"]
    return order_status in cancellable_statuses

def can_return_order(order_status: str, return_eligible: bool) -> bool:
    """Check if order can be returned"""
    returnable_statuses = ["Delivered"]
    return order_status in returnable_statuses and return_eligible

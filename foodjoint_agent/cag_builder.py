"""
CAG Builder - Build Cache-Augmented Generation context
Embeds policies and static data in system prompt
"""
import json
import logging
from pathlib import Path
from functools import lru_cache

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"

@lru_cache(maxsize=1)
def build_policy_context() -> str:
    """
    Build formatted policy context from company_return_refund_policy.json

    Returns:
        Formatted policy text for embedding
    """
    try:
        with open(DATA_DIR / "company_return_refund_policy.json", "r", encoding="utf-8") as f:
            policy_data = json.load(f)

        sections = policy_data.get("sections", {})

        # Format policies
        policy_text = """
==================================================
COMPANY POLICIES (Always Available - No Tool Calls Needed)
==================================================

### RETURN & REFUND POLICIES
{description}

### ELIGIBILITY & TIMELINE
• Return Window: {return_window}
• Condition: {condition}
• Exceptions: {exceptions}

### PROCESS FOR RETURNS
• Initiating Return: {initiating_return}
• Authorization: {authorization}
• Shipping Costs: {shipping_costs}

### REFUNDS & EXCHANGES
• Modes of Refund: {modes_of_refund}
• Processing Time: {processing_time}
• Exchanges: {exchanges}

==================================================
""".format(
            description=sections.get("return_and_refund_policies", {}).get("description", ""),
            return_window=sections.get("eligibility_and_timeline", {}).get("return_window", ""),
            condition=sections.get("eligibility_and_timeline", {}).get("condition", ""),
            exceptions=sections.get("eligibility_and_timeline", {}).get("exceptions", ""),
            initiating_return=sections.get("process_for_returns", {}).get("initiating_return", ""),
            authorization=sections.get("process_for_returns", {}).get("authorization", ""),
            shipping_costs=sections.get("process_for_returns", {}).get("shipping_costs", ""),
            modes_of_refund=sections.get("refunds_and_exchanges", {}).get("modes_of_refund", ""),
            processing_time=sections.get("refunds_and_exchanges", {}).get("processing_time", ""),
            exchanges=sections.get("refunds_and_exchanges", {}).get("exchanges", "")
        )

        return policy_text.strip()

    except Exception as e:
        logger.error(f"Error building policy context: {e}")
        return "Error loading policies"

@lru_cache(maxsize=1)
def build_categories_context() -> str:
    """
    Build product categories list

    Returns:
        Formatted categories text
    """
    categories = [
        "Electronics",
        "Clothing",
        "Home & Kitchen",
        "Beauty & Personal Care",
        "Sports & Fitness"
    ]

    return """
==================================================
PRODUCT CATEGORIES
==================================================
{categories}

Use these exact category names when searching products.
==================================================
""".format(categories="\n".join([f"• {cat}" for cat in categories])).strip()

@lru_cache(maxsize=1)
def build_order_status_context() -> str:
    """
    Build order status definitions

    Returns:
        Formatted order status text
    """
    return """
==================================================
ORDER STATUS DEFINITIONS
==================================================
• Placed: Order confirmed, payment received, preparing for shipment
• Shipped: Order dispatched from warehouse, in transit
• Out for Delivery: With delivery partner, arriving today
• Delivered: Successfully delivered to customer
• Cancelled: Order cancelled by customer or system

CANCELLATION POLICY:
• Only orders with status "Placed" can be cancelled
• Orders that are "Shipped", "Out for Delivery", or "Delivered" cannot be cancelled
• For shipped/delivered orders, customer must initiate a return instead

RETURN ELIGIBILITY:
• Only "Delivered" orders can be returned
• Must be within 30 days of delivery
• Product must be return-eligible (check product.return_eligible field)
==================================================
""".strip()

@lru_cache(maxsize=1)
def build_cag_context() -> str:
    """
    Build complete CAG context (policies + categories + status definitions)

    Returns:
        Complete formatted context
    """
    return f"""
{build_policy_context()}

{build_categories_context()}

{build_order_status_context()}
"""

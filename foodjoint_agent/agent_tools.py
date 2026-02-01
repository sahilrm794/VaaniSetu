"""
Customer Support Tools - All tools available to the voice agent
"""
import logging
from typing import Optional
from foodjoint_agent.managers.product_manager import get_product_manager
from foodjoint_agent.managers.order_manager import get_order_manager
from foodjoint_agent.managers.faq_manager import get_faq_manager
from foodjoint_agent.managers.session_manager import SessionManager

logger = logging.getLogger(__name__)

# Tool implementations

def search_products_by_name(query: str, limit: int = 5, session: Optional[SessionManager] = None) -> str:
    """
    Search for products by name using fuzzy matching

    Args:
        query: Product name or search term
        limit: Maximum number of results to return (default: 5)
        session: Session manager for context tracking

    Returns:
        Formatted string with search results
    """
    pm = get_product_manager()
    products = pm.search_by_name(query, limit=limit)

    if not products:
        return f"No products found matching '{query}'. Please try a different search term or browse by category."

    # Track searches in session
    if session and products:
        for product in products[:3]:  # Track top 3
            session.add_product_search(product["product_id"], product["product_name"])

    # Format results
    lines = [f"Found {len(products)} product(s) matching '{query}':\n"]

    for idx, product in enumerate(products, 1):
        stock_status = "In stock" if product["stock_available"] > 0 else "Out of stock"
        price = f"${product['price']:.2f}"

        lines.append(
            f"{idx}. {product['product_name']} ({product['category']})\n"
            f"   Price: {price} | Rating: {product['rating']:.1f}/5.0 ({product['review_count']} reviews)\n"
            f"   Stock: {stock_status} | Product ID: {product['product_id']}"
        )

    return "\n".join(lines)


def search_products_by_category(
    category: str,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    query: Optional[str] = None,
    limit: int = 10,
    session: Optional[SessionManager] = None
) -> str:
    """
    Search products by category with optional price filtering and name search

    Args:
        category: Product category (Electronics, Clothing, Home & Kitchen, Beauty & Personal Care, Sports & Fitness)
        price_min: Minimum price (optional)
        price_max: Maximum price (optional)
        query: Optional search term to filter by product name within category
        limit: Maximum number of results (default: 10)
        session: Session manager

    Returns:
        Formatted string with search results
    """
    pm = get_product_manager()
    products = pm.search_by_category(category, price_min, price_max, limit=limit)

    # If query is provided, filter products by name
    if query and products:
        query_lower = query.lower()
        products = [p for p in products if query_lower in p['product_name'].lower()]

    if not products:
        price_range = ""
        if price_min and price_max:
            price_range = f" in price range ${price_min:.2f} - ${price_max:.2f}"
        elif price_min:
            price_range = f" above ${price_min:.2f}"
        elif price_max:
            price_range = f" below ${price_max:.2f}"

        return f"No products found in category '{category}'{price_range}. Try a different category or price range."

    # Track in session
    if session and products:
        for product in products[:3]:
            session.add_product_search(product["product_id"], product["product_name"])

    # Format results
    price_filter = ""
    if price_min or price_max:
        if price_min and price_max:
            price_filter = f" (${price_min:.2f} - ${price_max:.2f})"
        elif price_min:
            price_filter = f" (above ${price_min:.2f})"
        else:
            price_filter = f" (below ${price_max:.2f})"

    lines = [f"Found {len(products)} product(s) in '{category}'{price_filter}:\n"]

    for idx, product in enumerate(products, 1):
        stock_status = "In stock" if product["stock_available"] > 0 else "Out of stock"

        lines.append(
            f"{idx}. {product['product_name']}\n"
            f"   Price: ${product['price']:.2f} | Rating: {product['rating']:.1f}/5.0\n"
            f"   {stock_status} | Product ID: {product['product_id']}"
        )

    return "\n".join(lines)


def get_product_details(product_id: str, session: Optional[SessionManager] = None) -> str:
    """
    Get detailed information about a specific product

    Args:
        product_id: Product ID (e.g., P1001)
        session: Session manager

    Returns:
        Formatted product details
    """
    pm = get_product_manager()
    product = pm.get_product_details(product_id)

    if not product:
        return f"Product {product_id} not found. Please verify the Product ID."

    # Track in session
    if session:
        session.add_product_search(product["product_id"], product["product_name"])

    # Format details
    stock_status = "In stock" if product["stock_available"] > 0 else "Out of stock"
    if 0 < product["stock_available"] < 5:
        stock_status = f"Low stock ({product['stock_available']} units remaining)"

    discount_info = ""
    if product.get("discount_percentage"):
        discount_info = f"\n• Discount: {product['discount_percentage']}% off"

    return_info = "Eligible for return" if product["return_eligible"] else "Not eligible for return (hygiene/safety reasons)"

    return f"""
Product Details for {product['product_name']}:
• Category: {product['category']}
• Price: ${product['price']:.2f}{discount_info}
• Rating: {product['rating']:.1f}/5.0 ({product['review_count']} customer reviews)
• Stock Status: {stock_status}
• Delivery Time: {product['delivery_time_days']} days
• Return Policy: {return_info}
• Description: {product['description']}
• Product ID: {product['product_id']}
""".strip()


def check_product_availability(product_id: str) -> str:
    """
    Check if a product is in stock

    Args:
        product_id: Product ID

    Returns:
        Stock availability message
    """
    pm = get_product_manager()
    result = pm.check_availability(product_id)

    return result["message"]


def get_product_faqs(product_id: str) -> str:
    """
    Get frequently asked questions for a specific product

    Args:
        product_id: Product ID

    Returns:
        Formatted FAQs
    """
    fm = get_faq_manager()
    faqs = fm.get_product_faqs(product_id)

    if not faqs:
        return f"No FAQs available for product {product_id}."

    # Get product name
    pm = get_product_manager()
    product = pm.get_product_details(product_id)
    product_name = product["product_name"] if product else product_id

    lines = [f"FAQs for {product_name}:\n"]

    for idx, faq in enumerate(faqs, 1):
        lines.append(f"{idx}. Q: {faq['question']}")
        lines.append(f"   A: {faq['answer']}\n")

    return "\n".join(lines)


def track_order(order_id: str, session: Optional[SessionManager] = None) -> str:
    """
    Track an order by Order ID

    Args:
        order_id: Order ID (e.g., O0001)
        session: Session manager

    Returns:
        Order status and tracking information
    """
    om = get_order_manager()
    order = om.get_order(order_id)

    if not order:
        return f"Order {order_id} not found. Please verify your Order ID or try searching by Customer ID."

    # Track in session and identify customer
    if session:
        session.add_order_lookup(order_id)
        session.set_customer_id(order["customer_id"])

    # Format order info
    items_list = [f"  - {item['product_name']} (Quantity: {item['quantity']})" for item in order["items"]]
    items_text = "\n".join(items_list)

    delivery_info = ""
    if order["delivery_date"]:
        delivery_info = f"\n• Expected Delivery: {order['delivery_date']}"

    return f"""
Order Status for {order_id}:
• Status: {order['order_status']}
• Order Date: {order['order_date']}{delivery_info}
• Total Amount: ${order['total_amount']:.2f}
• Customer ID: {order['customer_id']}

Items Ordered:
{items_text}
""".strip()


def get_customer_orders(customer_id: str, limit: int = 5, session: Optional[SessionManager] = None) -> str:
    """
    Get recent orders for a customer

    Args:
        customer_id: Customer ID (e.g., C0001)
        limit: Number of recent orders to return (default: 5)
        session: Session manager

    Returns:
        List of customer's recent orders
    """
    om = get_order_manager()
    orders = om.get_customer_orders(customer_id, limit=limit)

    if not orders:
        return f"No orders found for Customer {customer_id}."

    # Track in session
    if session:
        session.set_customer_id(customer_id)
        for order in orders[:3]:
            session.add_order_lookup(order["order_id"])

    lines = [f"Recent orders for Customer {customer_id}:\n"]

    for idx, order in enumerate(orders, 1):
        items_count = len(order["items"])
        items_preview = order["items"][0]["product_name"] if items_count == 1 else f"{items_count} items"

        lines.append(
            f"{idx}. Order {order['order_id']}\n"
            f"   Status: {order['order_status']} | Date: {order['order_date']}\n"
            f"   Total: ${order['total_amount']:.2f} | Items: {items_preview}"
        )

    return "\n".join(lines)


def get_order_details(order_id: str, session: Optional[SessionManager] = None) -> str:
    """
    Get detailed information about an order (similar to track_order but more comprehensive)

    Args:
        order_id: Order ID
        session: Session manager

    Returns:
        Detailed order information
    """
    return track_order(order_id, session)


def cancel_order(order_id: str, reason: str, session: Optional[SessionManager] = None) -> str:
    """
    Cancel an order (policy-aware)

    Args:
        order_id: Order ID to cancel
        reason: Reason for cancellation
        session: Session manager

    Returns:
        Cancellation result message
    """
    om = get_order_manager()
    result = om.cancel_order(order_id, reason)

    # Track in session
    if session and result["success"]:
        session.add_order_lookup(order_id)

    return result["message"]


def initiate_return(order_id: str, product_id: str, reason: str, session: Optional[SessionManager] = None) -> str:
    """
    Initiate return for a product (policy-aware)

    Args:
        order_id: Order ID
        product_id: Product ID to return
        reason: Reason for return
        session: Session manager

    Returns:
        Return initiation result
    """
    om = get_order_manager()
    result = om.initiate_return(order_id, product_id, reason)

    # Track in session
    if session and result["success"]:
        session.add_order_lookup(order_id)

    return result["message"]


def search_faqs(query: str, limit: int = 5) -> str:
    """
    Search across all product FAQs

    Args:
        query: Search query
        limit: Maximum number of results

    Returns:
        Relevant FAQs
    """
    fm = get_faq_manager()
    faqs = fm.search_all_faqs(query, limit=limit)

    if not faqs:
        return f"No FAQs found matching '{query}'. Please try different keywords."

    lines = [f"Found {len(faqs)} FAQ(s) matching '{query}':\n"]

    for idx, faq in enumerate(faqs, 1):
        lines.append(
            f"{idx}. Product: {faq['product_name']}\n"
            f"   Q: {faq['question']}\n"
            f"   A: {faq['answer']}\n"
        )

    return "\n".join(lines)


def get_all_categories() -> str:
    """
    Get list of all available product categories

    Returns:
        List of categories
    """
    pm = get_product_manager()
    categories = pm.get_all_categories()

    return "Available product categories:\n" + "\n".join([f"• {cat}" for cat in categories])

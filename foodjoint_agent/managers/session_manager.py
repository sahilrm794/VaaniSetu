"""
Session Manager - Handle conversation context per session
"""
import logging
from typing import List, Dict, Optional, Any
from collections import deque

logger = logging.getLogger(__name__)

class SessionManager:
    """Manage session context and conversation history"""

    def __init__(self, session_id: str, max_context_size: int = 5):
        self.session_id = session_id
        self.customer_id: Optional[str] = None
        self.conversation_history: deque = deque(maxlen=max_context_size)
        self.recent_product_searches: deque = deque(maxlen=5)
        self.recent_order_lookups: deque = deque(maxlen=3)
        self.current_intent: Optional[str] = None
        self.context: Dict[str, Any] = {}

    def add_conversation_turn(self, role: str, text: str):
        """Add a conversation turn to history"""
        self.conversation_history.append({
            "role": role,
            "text": text
        })

    def add_product_search(self, product_id: str, product_name: str):
        """Track a product search"""
        self.recent_product_searches.append({
            "product_id": product_id,
            "product_name": product_name
        })

    def add_order_lookup(self, order_id: str):
        """Track an order lookup"""
        if order_id not in [o for o in self.recent_order_lookups]:
            self.recent_order_lookups.append(order_id)

    def set_customer_id(self, customer_id: str):
        """Set identified customer ID"""
        self.customer_id = customer_id
        logger.info(f"Session {self.session_id}: Identified customer {customer_id}")

    def set_intent(self, intent: str):
        """Set current user intent"""
        self.current_intent = intent

    def get_context_summary(self) -> str:
        """Get formatted context summary"""
        parts = []

        if self.customer_id:
            parts.append(f"Customer ID: {self.customer_id}")

        if self.recent_order_lookups:
            parts.append(f"Recent orders viewed: {', '.join(list(self.recent_order_lookups))}")

        if self.recent_product_searches:
            products = [p["product_name"] for p in list(self.recent_product_searches)]
            parts.append(f"Recent products viewed: {', '.join(products[:3])}")

        return " | ".join(parts) if parts else "No context yet"

    def get_last_order(self) -> Optional[str]:
        """Get most recently looked up order"""
        return self.recent_order_lookups[-1] if self.recent_order_lookups else None

    def get_last_product(self) -> Optional[Dict[str, str]]:
        """Get most recently searched product"""
        return self.recent_product_searches[-1] if self.recent_product_searches else None

    def clear_context(self):
        """Clear session context"""
        self.conversation_history.clear()
        self.recent_product_searches.clear()
        self.recent_order_lookups.clear()
        self.current_intent = None
        self.context.clear()
        logger.info(f"Session {self.session_id}: Context cleared")

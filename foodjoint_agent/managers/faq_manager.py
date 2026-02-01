"""
FAQ Manager - Handle FAQ operations
"""
import sqlite3
import logging
from typing import List, Dict, Any
from foodjoint_agent.db.db_utils import get_connection
from foodjoint_agent.utils.fuzzy_search import fuzzy_match

logger = logging.getLogger(__name__)

class FAQManager:
    """Manage FAQ operations"""

    def get_product_faqs(self, product_id: str) -> List[Dict[str, Any]]:
        """
        Get all FAQs for a product

        Args:
            product_id: Product ID

        Returns:
            List of FAQ dictionaries
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT question, answer
                FROM product_faqs
                WHERE product_id = ?
            """, (product_id,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting product FAQs: {e}")
            return []
        finally:
            conn.close()

    def search_all_faqs(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search across all FAQs

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of FAQ dictionaries with product info
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Get all FAQs with product names
            cursor.execute("""
                SELECT pf.product_id, p.product_name, pf.question, pf.answer
                FROM product_faqs pf
                JOIN products p ON pf.product_id = p.product_id
            """)

            all_faqs = cursor.fetchall()

            # Create searchable text for each FAQ
            faq_texts = []
            faq_map = {}

            for idx, row in enumerate(all_faqs):
                faq_text = f"{row['question']} {row['answer']}"
                faq_texts.append(faq_text)
                faq_map[faq_text] = dict(row)

            # Fuzzy match
            matches = fuzzy_match(query, faq_texts, threshold=0.5, limit=limit)

            results = []
            for faq_text, score in matches:
                faq = faq_map[faq_text].copy()
                faq["relevance_score"] = score
                results.append(faq)

            return results

        except Exception as e:
            logger.error(f"Error searching FAQs: {e}")
            return []
        finally:
            conn.close()

def get_faq_manager() -> FAQManager:
    """Get FAQManager instance"""
    return FAQManager()

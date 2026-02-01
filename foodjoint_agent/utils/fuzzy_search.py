"""
Fuzzy search utilities using rapidfuzz
"""
from rapidfuzz import fuzz, process
from typing import List, Tuple, Optional

def fuzzy_match(
    query: str,
    choices: List[str],
    threshold: float = 0.75,
    limit: int = 5
) -> List[Tuple[str, float]]:
    """
    Perform fuzzy matching on a list of choices

    Args:
        query: Search query
        choices: List of strings to match against
        threshold: Minimum similarity score (0-1)
        limit: Maximum number of results

    Returns:
        List of tuples (matched_string, score)
    """
    if not query or not choices:
        return []

    # Use WRatio for best overall performance
    results = process.extract(
        query,
        choices,
        scorer=fuzz.WRatio,
        limit=limit,
        score_cutoff=threshold * 100  # rapidfuzz uses 0-100 scale
    )

    # Convert to 0-1 scale
    return [(match, score / 100.0) for match, score, _ in results]

def get_best_match(
    query: str,
    choices: List[str],
    threshold: float = 0.75
) -> Optional[Tuple[str, float]]:
    """
    Get single best match

    Returns:
        Tuple (matched_string, score) or None if no match above threshold
    """
    results = fuzzy_match(query, choices, threshold, limit=1)
    return results[0] if results else None

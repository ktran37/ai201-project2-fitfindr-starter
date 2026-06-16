"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

from tools import search_listings, suggest_outfit, create_fit_card, compare_price, get_trend_insight
from memory import load_profile, update_profile_from_interaction, get_profile_summary


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
        "retry_adjustments": None,   # set if filters were loosened during retry
        "price_comparison": None,    # stretch: price fairness analysis
        "trend_insight": None,       # stretch: trend relevance note
        "profile_summary": None,     # stretch: user's learned style profile
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.
    """
    import re

    # Step 1: Initialize the session
    session = _new_session(query, wardrobe)

    # Step 2: Parse the user's query to extract description, size, and max_price
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # Step 3: Call search_listings with the parsed parameters
    results = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    # BRANCH: If no results, try retries with loosened constraints
    if not results:
        original_size = parsed["size"]
        original_price = parsed["max_price"]

        # Retry 1: Remove size filter, keep max_price
        if original_size is not None:
            results = search_listings(
                description=parsed["description"],
                size=None,
                max_price=parsed["max_price"],
            )
            session["search_results"] = results
            if results:
                session["retry_adjustments"] = (
                    f"Size filter ('{original_size}') was removed to find these results."
                )

        # Retry 2: Remove both size and max_price filters
        if not results and (original_size is not None or original_price is not None):
            results = search_listings(
                description=parsed["description"],
                size=None,
                max_price=None,
            )
            session["search_results"] = results
            if results:
                parts = []
                if original_size is not None:
                    parts.append("size")
                if original_price is not None:
                    parts.append("price")
                session["retry_adjustments"] = (
                    f"{' and '.join(parts).capitalize()} filter(s) were removed "
                    f"to find these results."
                )

        # All retries exhausted — set error and return
        if not results:
            size_str = f", size {original_size}" if original_size else ""
            price_str = f", max ${original_price:.0f}" if original_price is not None else ""
            session["error"] = (
                f"No listings matched '{parsed['description']}'"
                f"{size_str}{price_str} even after removing "
                f"size and price filters. Try different keywords."
            )
            return session

    # Step 4: Select the top result
    session["selected_item"] = results[0]

    # Step 5: Call suggest_outfit with the selected item and wardrobe
    outfit = suggest_outfit(session["selected_item"], session["wardrobe"])
    session["outfit_suggestion"] = outfit

    # Step 6: Call create_fit_card with the outfit suggestion and selected item
    card = create_fit_card(session["outfit_suggestion"], session["selected_item"])
    session["fit_card"] = card

    # Step 7 (stretch): Compare price against similar listings
    session["price_comparison"] = compare_price(session["selected_item"])

    # Step 8 (stretch): Get trend insight for the selected item
    session["trend_insight"] = get_trend_insight(session["selected_item"])

    # Step 9 (stretch): Load and update style profile memory
    profile = load_profile()
    update_profile_from_interaction(profile, session["selected_item"], session["wardrobe"])
    session["profile_summary"] = get_profile_summary(profile)

    # Step 10: Return the session
    return session


def _parse_query(query: str) -> dict:
    """
    Parse a natural language query to extract description, size, and max_price.

    Uses regex patterns to pull out structured fields, then treats the remainder
    as the free-text description.

    Args:
        query: Raw user query string.

    Returns:
        Dict with keys: description (str), size (str or None), max_price (float or None).
    """
    import re

    description = query.strip()
    size = None
    max_price = None

    # Extract price: $N, under $N, max $N, under N dollars, etc.
    price_match = re.search(
        r'(?:under\s+)?\$?\s*(\d+)(?:\s*(?:dollars?|bucks?))?'
        r'|(?:max|under)\s+\$?\s*(\d+)',
        description,
        re.IGNORECASE,
    )
    if price_match:
        price_val = price_match.group(1) or price_match.group(2)
        if price_val:
            max_price = float(price_val)
            # Remove the price phrase from the description
            description = description[:price_match.start()] + description[price_match.end():]

    # Extract size: "size M", "size medium", "size S/M", standalone size words
    size_match = re.search(
        r'size\s+([^\s,]+(?:\s*/\s*[^\s,]+)?)'
        r'|(?<!\w)(XS|S|M|L|XL|XXL|small|medium|large)(?!\w)',
        description,
        re.IGNORECASE,
    )
    if size_match:
        size = (size_match.group(1) or size_match.group(2)).strip()
        # Remove the size phrase from the description
        description = description[:size_match.start()] + description[size_match.end():]

    # Clean up the description: remove extra spaces, punctuation artifacts
    description = re.sub(r'\s+', ' ', description).strip()
    description = re.sub(r'^[,.\s]+|[,.\s]+$', '', description)
    # Remove leading/trailing connectors
    description = re.sub(r'^(and|or|in|for|with)\s+', '', description, flags=re.IGNORECASE).strip()

    if not description:
        description = query.strip()

    return {
        "description": description,
        "size": size,
        "max_price": max_price,
    }


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")

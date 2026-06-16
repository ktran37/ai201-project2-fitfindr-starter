"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: Optional[str] = None,
    max_price: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform
    """
    listings = load_listings()
    keywords = description.lower().split()

    # Step 1: Filter by max_price and size
    filtered = []
    for item in listings:
        # Price filter
        if max_price is not None and item["price"] > max_price:
            continue
        # Size filter (case-insensitive substring match)
        if size is not None and size.lower() not in item["size"].lower():
            continue
        filtered.append(item)

    # Step 2: Score each listing by keyword overlap
    # Search across title, description, and style_tags
    scored = []
    for item in filtered:
        # Build a searchable text blob from relevant fields
        search_text = (
            item["title"].lower()
            + " "
            + item["description"].lower()
            + " "
            + " ".join(tag.lower() for tag in item["style_tags"])
        )
        score = 0
        for kw in keywords:
            if kw in search_text:
                score += 1
        if score > 0:
            scored.append((score, item))

    # Step 3: Sort by score descending, return just the listing dicts
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _score, item in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: Dict[str, Any], wardrobe: Dict[str, Any]) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.
    """
    try:
        client = _get_groq_client()

        # Build a description of the new item
        item_desc = (
            f"Item: \"{new_item['title']}\"\n"
            f"Category: {new_item['category']}\n"
            f"Colors: {', '.join(new_item['colors'])}\n"
            f"Style tags: {', '.join(new_item['style_tags'])}\n"
            f"Price: ${new_item['price']:.2f} from {new_item['platform']}\n"
            f"Condition: {new_item['condition']}"
        )

        wardrobe_items = wardrobe.get("items", [])

        if not wardrobe_items:
            # Empty wardrobe: ask for general styling advice
            prompt = (
                f"A user is considering buying this thrifted item:\n\n"
                f"{item_desc}\n\n"
                f"The user has no wardrobe items saved yet. "
                f"Give 1–2 paragraphs of general styling advice for this piece: "
                f"what kinds of items pair well with it, what vibe or aesthetic it suits, "
                f"and what occasions it would work for. "
                f"Be specific and practical — name actual garment types and color combinations. "
                f"Do NOT say 'since your wardrobe is empty' or mention the empty wardrobe. "
                f"Just give the styling advice naturally."
            )
        else:
            # Format wardrobe items for the prompt
            wardrobe_lines = []
            for w_item in wardrobe_items:
                notes_str = f" — {w_item['notes']}" if w_item.get("notes") else ""
                wardrobe_lines.append(
                    f"- {w_item['id']}: {w_item['name']} "
                    f"({w_item['category']}, colors: {', '.join(w_item['colors'])}, "
                    f"tags: {', '.join(w_item['style_tags'])}{notes_str})"
                )
            wardrobe_text = "\n".join(wardrobe_lines)

            prompt = (
                f"A user is considering buying this thrifted item:\n\n"
                f"{item_desc}\n\n"
                f"The user's existing wardrobe contains these items:\n\n"
                f"{wardrobe_text}\n\n"
                f"Suggest 1–2 complete outfit combinations using the new item paired with "
                f"pieces from the wardrobe. For each outfit, name the specific wardrobe items "
                f"by their name (and ID in parentheses). Explain why the pieces work together — "
                f"mention colors, silhouettes, and style cohesion. "
                f"Be specific and practical. Keep it to 1–2 paragraphs."
            )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        return (
            "Sorry, I couldn't generate an outfit suggestion right now. "
            f"Please try again. (Error: {e})"
        )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: Dict[str, Any]) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)
    """
    # Guard against empty or whitespace-only outfit
    if not outfit or not outfit.strip():
        return (
            "Couldn't generate a fit card — the outfit description was empty. "
            "Try running the search again."
        )

    try:
        client = _get_groq_client()

        item_desc = (
            f"Item: \"{new_item['title']}\"\n"
            f"Price: ${new_item['price']:.2f}\n"
            f"Platform: {new_item['platform']}\n"
            f"Category: {new_item['category']}\n"
            f"Style: {', '.join(new_item['style_tags'])}\n"
            f"Colors: {', '.join(new_item['colors'])}"
        )

        prompt = (
            f"Write a short, casual social media caption (2–4 sentences) for a thrifted outfit. "
            f"Sound like a real person posting an OOTD — authentic, not like a product description.\n\n"
            f"Item details:\n{item_desc}\n\n"
            f"Outfit idea:\n{outfit}\n\n"
            f"Requirements:\n"
            f"- Mention the item name, price (${new_item['price']:.2f}), and platform "
            f"({new_item['platform']}) naturally — once each, don't force them.\n"
            f"- Capture the outfit vibe in specific, sensory terms.\n"
            f"- Use casual language: contractions, lowercase, emojis are fine.\n"
            f"- Sound like a text to a friend, not a sponsored post.\n"
            f"- 2–4 sentences only. No hashtags unless they feel natural.\n"
            f"- Vary the wording — don't use the same template every time."
        )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        return (
            "Sorry, I couldn't create a fit card right now. "
            f"Please try again. (Error: {e})"
        )


# ── Stretch Tool 4: compare_price ─────────────────────────────────────────────

def compare_price(new_item: Dict[str, Any]) -> str:
    """
    Estimate whether a listing's price is fair by comparing it to similar
    listings in the dataset (same category, similar style tags).

    Args:
        new_item: A listing dict (the item the user is considering buying).

    Returns:
        A string describing how the item's price compares to similar listings,
        including the average price, the price range, and a verdict (great deal,
        fair price, or overpriced).
    """
    listings = load_listings()
    category = new_item.get("category", "")
    item_tags = set(tag.lower() for tag in new_item.get("style_tags", []))
    item_price = new_item.get("price", 0)

    # Find comparable listings: same category, at least one overlapping style tag
    comparables = []
    for listing in listings:
        if listing["id"] == new_item.get("id"):
            continue  # Don't compare to self
        if listing.get("category") != category:
            continue
        listing_tags = set(tag.lower() for tag in listing.get("style_tags", []))
        if not item_tags & listing_tags:  # No style overlap
            continue
        comparables.append(listing["price"])

    if not comparables:
        # Fall back to same-category only
        for listing in listings:
            if listing["id"] == new_item.get("id"):
                continue
            if listing.get("category") == category:
                comparables.append(listing["price"])

    if not comparables:
        return (
            f"Not enough data to compare prices for {category} items. "
            f"This listing is ${item_price:.2f}."
        )

    avg_price = sum(comparables) / len(comparables)
    min_price = min(comparables)
    max_price = max(comparables)

    # Determine verdict
    if item_price <= avg_price * 0.85:
        verdict = "🔥 Great deal"
        detail = "well below"
    elif item_price <= avg_price * 1.05:
        verdict = "✅ Fair price"
        detail = "right around"
    elif item_price <= avg_price * 1.25:
        verdict = "⚠️  Slightly high"
        detail = "a bit above"
    else:
        verdict = "💸 Overpriced"
        detail = "significantly above"

    return (
        f"{verdict} — This {category} item is priced at ${item_price:.2f}, "
        f"which is {detail} the average of ${avg_price:.2f} "
        f"for similar {category} items "
        f"(range: ${min_price:.2f}–${max_price:.2f}, "
        f"based on {len(comparables)} comparable listings)."
    )


# ── Stretch Tool 5: get_trend_insight ─────────────────────────────────────────

def get_trend_insight(item: Dict[str, Any]) -> str:
    """
    Generate a short trend-awareness note for a given item by calling the LLM
    with context about current popular styles in the item's category and tags.

    Since we don't have live access to a fashion platform API, this tool uses
    the LLM's training knowledge (which includes fashion trend data through
    early 2025) to surface what styles are currently popular that relate to
    the item.

    Args:
        item: A listing dict (the item the user is considering buying).

    Returns:
        A 2–3 sentence string describing current trend relevance for this item.
        If the LLM call fails, returns a fallback message.
    """
    try:
        client = _get_groq_client()

        item_desc = (
            f"Item: \"{item['title']}\"\n"
            f"Category: {item['category']}\n"
            f"Style tags: {', '.join(item['style_tags'])}\n"
            f"Colors: {', '.join(item['colors'])}\n"
            f"Platform: {item['platform']}"
        )

        prompt = (
            f"Based on fashion trends through 2025, write 2–3 short, specific sentences "
            f"about how this item fits into current style trends. Be honest — if it's "
            f"not currently trending, say what kind of aesthetic it suits instead.\n\n"
            f"{item_desc}\n\n"
            f"Focus on: what's currently popular in this category, whether these style "
            f"tags are trending, and what kind of person would wear this now. "
            f"Keep it punchy and useful — like a quick trend check, not a fashion essay."
        )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        return (
            f"Couldn't fetch trend data right now. "
            f"This {item.get('category', 'item')} has tags: "
            f"{', '.join(item.get('style_tags', []))}."
        )

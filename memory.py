"""
memory.py

Style profile memory for FitFindr. Allows the agent to remember a user's
style preferences across sessions by persisting them to a JSON file.

The profile stores:
- style_tags: list of style descriptors the user prefers (e.g., ["streetwear", "vintage"])
- favorite_colors: list of preferred colors
- favorite_categories: list of preferred categories
- saved_wardrobe: a copy of the last wardrobe used (optional)
- interaction_count: how many times the user has used FitFindr
"""

import json
import os
from typing import Optional, Dict, Any, List

# Resolve the path to the memory file relative to the project root
_MEMORY_FILE = os.path.join(os.path.dirname(__file__), "data", "style_profile.json")


def _default_profile() -> Dict[str, Any]:
    """Return a fresh, empty style profile."""
    return {
        "style_tags": [],
        "favorite_colors": [],
        "favorite_categories": [],
        "saved_wardrobe": None,
        "interaction_count": 0,
    }


def load_profile() -> Dict[str, Any]:
    """
    Load the user's style profile from disk.

    Returns:
        A profile dict. If no profile exists yet, returns a default empty profile.
    """
    if not os.path.exists(_MEMORY_FILE):
        return _default_profile()
    try:
        with open(_MEMORY_FILE, "r", encoding="utf-8") as f:
            profile = json.load(f)
        # Ensure all keys exist (backward compatibility)
        defaults = _default_profile()
        for key in defaults:
            if key not in profile:
                profile[key] = defaults[key]
        return profile
    except (json.JSONDecodeError, IOError):
        return _default_profile()


def save_profile(profile: Dict[str, Any]) -> None:
    """
    Persist the style profile to disk.

    Args:
        profile: The profile dict to save.
    """
    os.makedirs(os.path.dirname(_MEMORY_FILE), exist_ok=True)
    with open(_MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)


def update_profile_from_interaction(
    profile: Dict[str, Any],
    selected_item: Dict[str, Any],
    wardrobe: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Update the style profile based on a completed interaction.

    Learns from the item the user selected: extracts style tags, colors,
    and category to build a preference profile over time.

    Args:
        profile: The current profile dict.
        selected_item: The listing dict the user selected (top search result).
        wardrobe: Optional wardrobe dict to save.

    Returns:
        The updated profile dict.
    """
    profile["interaction_count"] += 1

    # Learn style tags (add new ones, keep existing)
    for tag in selected_item.get("style_tags", []):
        if tag.lower() not in [t.lower() for t in profile["style_tags"]]:
            profile["style_tags"].append(tag)

    # Learn favorite colors (add new ones)
    for color in selected_item.get("colors", []):
        if color.lower() not in [c.lower() for c in profile["favorite_colors"]]:
            profile["favorite_colors"].append(color)

    # Learn favorite categories (add new ones)
    cat = selected_item.get("category", "")
    if cat and cat.lower() not in [c.lower() for c in profile["favorite_categories"]]:
        profile["favorite_categories"].append(cat)

    # Save wardrobe if provided
    if wardrobe is not None:
        profile["saved_wardrobe"] = wardrobe

    save_profile(profile)
    return profile


def get_profile_summary(profile: Dict[str, Any]) -> str:
    """
    Generate a human-readable summary of the user's style profile.

    Args:
        profile: The profile dict from load_profile().

    Returns:
        A string summarizing the user's learned preferences, or a message
        if the profile is empty.
    """
    if profile["interaction_count"] == 0:
        return "No style profile yet — keep using FitFindr to build one!"

    parts = []
    if profile["style_tags"]:
        parts.append(f"Style: {', '.join(profile['style_tags'][:8])}")
    if profile["favorite_colors"]:
        parts.append(f"Colors: {', '.join(profile['favorite_colors'][:6])}")
    if profile["favorite_categories"]:
        parts.append(f"Categories: {', '.join(profile['favorite_categories'][:5])}")

    summary = (
        f"📊 Style profile (from {profile['interaction_count']} interactions):\n"
        + "\n".join(f"  • {p}" for p in parts)
    )

    if profile["saved_wardrobe"]:
        item_count = len(profile["saved_wardrobe"].get("items", []))
        summary += f"\n  • Saved wardrobe: {item_count} items"

    return summary


def reset_profile() -> Dict[str, Any]:
    """
    Reset the style profile to defaults and save.

    Returns:
        A fresh default profile.
    """
    profile = _default_profile()
    save_profile(profile)
    return profile

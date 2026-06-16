"""
tests/test_tools.py

Pytest tests for the three FitFindr tools.
Run with: pytest tests/ -v
"""

import pytest
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings tests ─────────────────────────────────────────────────────

def test_search_returns_results():
    """A reasonable query should return at least one result."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0
    # Verify result structure
    for item in results:
        assert "id" in item
        assert "title" in item
        assert "price" in item
        assert "platform" in item


def test_search_empty_results():
    """An impossible query should return an empty list, not raise an exception."""
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    """All returned items should be at or under max_price."""
    results = search_listings("jacket", size=None, max_price=50)
    assert all(item["price"] <= 50 for item in results)


def test_search_size_filter():
    """Size filter should be case-insensitive substring match."""
    results = search_listings("jeans", size="W30", max_price=None)
    assert len(results) > 0
    for item in results:
        assert "30" in item["size"] or "w30" in item["size"].lower()


def test_search_relevance_sorting():
    """Results should be sorted by relevance — first result should be more
    relevant than later results for obvious queries."""
    results = search_listings("denim jacket", size=None, max_price=None)
    if len(results) >= 2:
        # The first result should have 'denim' and 'jacket' in its title/description
        first_text = (results[0]["title"] + " " + results[0]["description"]).lower()
        assert "denim" in first_text or "jacket" in first_text


def test_search_none_filters():
    """None size and None max_price should not crash or filter anything out."""
    results_all = search_listings("", size=None, max_price=None)
    results_filtered = search_listings("vintage", size=None, max_price=None)
    # With empty description, no keywords match → empty
    # With 'vintage', should find some
    assert isinstance(results_filtered, list)
    assert len(results_filtered) > 0


# ── suggest_outfit tests ──────────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe():
    """Should return a non-empty string with outfit suggestions."""
    results = search_listings("vintage graphic tee", max_price=30)
    assert len(results) > 0
    item = results[0]
    wardrobe = get_example_wardrobe()
    outfit = suggest_outfit(item, wardrobe)
    assert isinstance(outfit, str)
    assert len(outfit) > 0


def test_suggest_outfit_empty_wardrobe():
    """Empty wardrobe should return general styling advice, not crash."""
    results = search_listings("vintage graphic tee", max_price=30)
    assert len(results) > 0
    item = results[0]
    outfit = suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(outfit, str)
    assert len(outfit) > 0
    # Should not mention "empty" or "no items"
    assert "empty" not in outfit.lower() or "wardrobe" not in outfit.lower()


def test_suggest_outfit_returns_different_for_different_inputs():
    """Different items should produce different suggestions."""
    results1 = search_listings("graphic tee", max_price=30)
    results2 = search_listings("flannel", max_price=30)
    if len(results1) > 0 and len(results2) > 0:
        wardrobe = get_example_wardrobe()
        outfit1 = suggest_outfit(results1[0], wardrobe)
        outfit2 = suggest_outfit(results2[0], wardrobe)
        # They should be different strings
        assert outfit1 != outfit2


# ── create_fit_card tests ─────────────────────────────────────────────────────

def test_create_fit_card_normal():
    """Should return a non-empty caption string."""
    results = search_listings("vintage graphic tee", max_price=30)
    item = results[0]
    wardrobe = get_example_wardrobe()
    outfit = suggest_outfit(item, wardrobe)
    card = create_fit_card(outfit, item)
    assert isinstance(card, str)
    assert len(card) > 0


def test_create_fit_card_empty_outfit():
    """Empty outfit string should return an error message, not crash."""
    results = search_listings("vintage graphic tee", max_price=30)
    item = results[0]
    card = create_fit_card("", item)
    assert isinstance(card, str)
    assert len(card) > 0
    assert "empty" in card.lower() or "couldn't" in card.lower()


def test_create_fit_card_whitespace_outfit():
    """Whitespace-only outfit should also be caught."""
    results = search_listings("vintage graphic tee", max_price=30)
    item = results[0]
    card = create_fit_card("   \n  \t  ", item)
    assert isinstance(card, str)
    assert len(card) > 0
    assert "empty" in card.lower() or "couldn't" in card.lower()

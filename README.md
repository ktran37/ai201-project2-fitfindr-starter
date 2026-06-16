# FitFindr 🛍️

An AI-powered agent that helps you find secondhand clothing, get outfit suggestions based on your existing wardrobe, and generate shareable fit card captions — all in one interaction.

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

Run the app:
```bash
python app.py
```

Run tests:
```bash
pytest tests/ -v
```

---

## Tool Inventory

### Tool 1: `search_listings(description, size, max_price)`

| Field | Detail |
|-------|--------|
| **Purpose** | Search the 40-item mock listings dataset for items matching a description, optional size, and optional max price. |
| **Inputs** | `description` (str): Free-text keywords for matching against listing titles, descriptions, and style tags. `size` (str \| None): Case-insensitive substring size filter (e.g., "M" matches "S/M"). `max_price` (float \| None): Maximum price ceiling, inclusive. |
| **Output** | `list[dict]` — Matching listings sorted by relevance score (keyword overlap), highest first. Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` if nothing matches. |
| **Failure mode** | Returns empty list `[]` — never raises an exception. The planning loop catches this and returns a helpful error message with suggestions. |

### Tool 2: `suggest_outfit(new_item, wardrobe)`

| Field | Detail |
|-------|--------|
| **Purpose** | Generate 1–2 outfit combinations pairing a thrifted item with pieces from the user's wardrobe. Uses Groq's `llama-3.3-70b-versatile` LLM. |
| **Inputs** | `new_item` (dict): A listing dict from `search_listings`. `wardrobe` (dict): A dict with an `items` key containing wardrobe item dicts (each with `id`, `name`, `category`, `colors`, `style_tags`, `notes`). |
| **Output** | `str` — A paragraph describing outfit combinations, referencing specific wardrobe items by name and ID. For empty wardrobes, returns general styling advice instead. |
| **Failure mode** | If wardrobe is empty: returns general styling advice (what kinds of pieces pair well, what vibe suits the item). If LLM call fails: returns a descriptive error string. |

### Tool 3: `create_fit_card(outfit, new_item)`

| Field | Detail |
|-------|--------|
| **Purpose** | Generate a short, casual social-media caption (2–4 sentences) for the thrifted outfit. Uses Groq LLM with higher temperature (0.9) for variety. |
| **Inputs** | `outfit` (str): The outfit suggestion string from `suggest_outfit`. `new_item` (dict): The listing dict for the thrifted item. |
| **Output** | `str` — A 2–4 sentence caption in casual OOTD style, mentioning the item name, price, and platform naturally. |
| **Failure mode** | If `outfit` is empty/whitespace: returns "Couldn't generate a fit card — the outfit description was empty. Try running the search again." If LLM call fails: returns a descriptive error string. |

---

## How the Planning Loop Works

The planning loop follows a strict linear pipeline with one critical branch:

1. **Initialize session** — Create a fresh session dict to hold all state for this interaction.
2. **Parse the query** — Extract `description`, `size`, and `max_price` from the user's natural language input using regex patterns.
3. **Call `search_listings`** — Pass the parsed parameters. Store results in the session.
4. **BRANCH — check results (with retry logic):**
   - **If empty (`[]`):** Enter retry loop:
     - **Retry 1:** Remove size filter, keep max_price. If results found, note "size filter removed" and continue.
     - **Retry 2:** Remove both size and max_price. If results found, note "size and price filters removed" and continue.
     - **All retries exhausted:** Set `session["error"]` with a message explaining what was tried. **Return immediately.** Do NOT call `suggest_outfit` or `create_fit_card`.
   - **If results exist (original or retry):** Set `session["selected_item"] = search_results[0]` (top-ranked match). Continue.
5. **Call `suggest_outfit`** — Pass the selected item and wardrobe. Store the result.
6. **Call `create_fit_card`** — Pass the outfit suggestion and selected item. Store the result.
7. **Return the session** — All three output fields are populated.

The sequence is deterministic — the only branch is the empty-results check after step 3. The agent never calls tools conditionally based on LLM output.

---

## State Management

All state lives in a single `session` dict created fresh for each interaction. Nothing is stored globally or persists between calls to `run_agent()`.

| Field | Type | Set by | Used by |
|-------|------|--------|---------|
| `query` | str | `_new_session()` | Reference |
| `parsed` | dict | Query parser | `search_listings` |
| `search_results` | list[dict] | `search_listings` | Branch check; top result → `selected_item` |
| `selected_item` | dict or None | Planning loop | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | dict | `_new_session()` | `suggest_outfit` |
| `outfit_suggestion` | str or None | `suggest_outfit` | `create_fit_card` |
| `fit_card` | str or None | `create_fit_card` | Final output |
| `error` | str or None | Planning loop (branch) | Checked by caller |
| `retry_adjustments` | str or None | Planning loop (retry) | Displayed in UI when filters were loosened |

**Data flow:** `search_listings` → `selected_item` → `suggest_outfit` → `outfit_suggestion` → `create_fit_card`. No tool reads from another tool directly — all data flows through the session dict.

---

## Error Handling

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No results match the query | Agent sets `session["error"]` to: "No listings matched your search for '[description]' (size [size], max $[price]). Try broadening your description, removing the size filter, or increasing your max price." Returns session early — does NOT call `suggest_outfit` or `create_fit_card`. |
| `suggest_outfit` | Wardrobe is empty | Tool detects `wardrobe["items"]` is empty and calls the LLM with a different prompt asking for general styling advice. Returns something like: "This graphic tee pairs well with light-wash baggy jeans and chunky sneakers for a streetwear look." Agent continues normally. |
| `create_fit_card` | Outfit input is empty or whitespace | Tool returns: "Couldn't generate a fit card — the outfit description was empty. Try running the search again." Agent stores this in `session["fit_card"]` and returns normally. |

**Concrete example from testing:** Querying "designer ballgown size XXS under $5" triggers the `search_listings` empty-results path. The agent returns: *"No listings matched your search for 'designer ballgown', size XXS, max $5. Try broadening your description, removing the size filter, or increasing your max price."* — and does not call the other two tools.

---

## Spec Reflection

**One way the spec helped me:** Writing out the exact conditional logic for the planning loop in `planning.md` before coding made implementation straightforward. When I gave the spec to the AI tool, the generated code matched the sequence exactly — the empty-results branch was the first thing I tested, and it worked correctly on the first run.

**One way implementation diverged from the spec:** The spec originally described extracting `description`, `size`, and `max_price` from the query, but I initially planned to parse size as a standalone word match only (e.g., "M", "large"). During implementation, I realized the dataset uses sizes like "S/M" and "W30 L30", so I expanded the size regex to also handle `size M` prefixed patterns and slashed sizes. This made the parser more robust without changing the tool interface.

---

## AI Usage

### Instance 1: Implementing `search_listings`

**What I gave the AI:** The Tool 1 spec block from `planning.md` (what it does, input parameters with types, return value structure, failure mode) plus the TODO steps in `tools.py` and the `load_listings()` helper from `utils/data_loader.py`.

**What it produced:** A function that loads listings, filters by `max_price` and `size` (case-insensitive substring), scores by keyword overlap across title/description/style_tags, drops zero-score results, and sorts by score descending.

**What I revised:** The initial implementation used `description.lower() in search_text` for scoring, which only gave a binary match. I changed it to split `description` into individual keywords and score each keyword independently, which produces better relevance ranking. I also added the `continue` pattern for the filter loop instead of building intermediate lists.

### Instance 2: Implementing the planning loop in `run_agent()`

**What I gave the AI:** The full Planning Loop section from `planning.md` (the 7-step conditional logic), the State Management table, the Architecture Mermaid diagram, and the TODO steps in `agent.py`.

**What it produced:** A `run_agent()` function following the exact 7-step sequence with the empty-results branch, plus a `_parse_query()` helper using regex to extract description, size, and max_price.

**What I revised:** The initial regex for price parsing was too greedy and would match numbers in the description (like "90s"). I tightened it to only match dollar-prefixed patterns (`$N`, `under $N`, `max $N`) and standalone numbers followed by "dollars" or "bucks". I also added cleanup logic to strip connector words ("and", "or", "in") from the parsed description.

---

## Project Structure

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   ├── wardrobe_schema.json   # Wardrobe format + example + empty template
│   └── style_profile.json     # Persisted user style profile (stretch)
├── utils/
│   └── data_loader.py         # load_listings(), get_example_wardrobe(), get_empty_wardrobe()
├── tests/
│   ├── __init__.py
│   └── test_tools.py          # 12 pytest tests covering all tools and failure modes
├── tools.py                   # search_listings, suggest_outfit, create_fit_card, compare_price, get_trend_insight
├── agent.py                   # run_agent() planning loop + _parse_query() + retry logic
├── memory.py                  # Style profile persistence (stretch)
├── app.py                     # Gradio UI with 6 output panels
├── planning.md                # Full spec (tools, loop, state, diagram, AI plan, stretch)
├── requirements.txt           # groq, python-dotenv, gradio, pytest
└── README.md                  # This file
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

---

## Stretch Feature: Retry Logic with Fallback

When `search_listings` returns no results, the agent automatically retries with progressively loosened constraints instead of immediately giving up:

| Attempt | Filters applied | What changes |
|---------|----------------|--------------|
| 1 (original) | description + size + max_price | None — user's exact query |
| 2 (retry 1) | description + max_price | Size filter removed |
| 3 (retry 2) | description only | Size and price filters removed |

If a retry succeeds, the UI displays a note like *"⚠️ Size filter ('XXS') was removed to find these results."* so the user understands why they're seeing results that don't perfectly match their query.

If all retries fail, the error message explains what was tried: *"No listings matched 'designer ballgown', size XXS, max $5 even after removing size and price filters. Try different keywords."*

**Example:** Querying "vintage graphic tee size XXS under $50" initially returns nothing (no XXS tees exist). Retry 1 removes the size filter and finds 29 matching tees. The user sees results with a note that the size filter was removed.

---

## Stretch Features

### 1. Price Comparison Tool (`compare_price`)

Compares the selected item's price against similar listings in the dataset (same category, overlapping style tags). Returns a verdict with the average price, range, and number of comparable listings.

| Verdict | Condition |
|---------|-----------|
| 🔥 Great deal | Price ≤ 85% of average |
| ✅ Fair price | Price within 5% of average |
| ⚠️ Slightly high | Price 5–25% above average |
| 💸 Overpriced | Price > 25% above average |

**Example:** "🔥 Great deal — This tops item is priced at $18.00, which is well below the average of $22.00 for similar tops items (range: $15.00–$35.00, based on 14 comparable listings)."

### 2. Style Profile Memory

Persists user style preferences across sessions by saving to `data/style_profile.json`. Each successful interaction learns from the selected item — accumulating style tags, colors, and categories. The profile grows over time and is displayed after each search.

**Example:** "📊 Style profile (from 3 interactions): Style: y2k, vintage, denim, streetwear | Colors: white, pink, light blue | Categories: tops, outerwear | Saved wardrobe: 10 items"

**Implementation:** `memory.py` with `load_profile()`, `save_profile()`, `update_profile_from_interaction()`, `get_profile_summary()`, and `reset_profile()`.

### 3. Trend Awareness (`get_trend_insight`)

Calls the Groq LLM with context about the selected item to surface current trend relevance. Uses the LLM's training knowledge to note whether the item's style tags are trending and what aesthetic it fits into.

**Example:** "The Y2K Baby Tee's vintage graphic vibe is still going strong, fitting right into the current nostalgia-driven fashion trend. Its pastel color palette and butterfly print are particularly on-point for Depop shoppers looking for unique, eclectic pieces."

### 4. Retry Logic with Fallback

When `search_listings` returns no results, the agent automatically retries with progressively loosened constraints. See the section above for full details.

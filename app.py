"""
app.py

Gradio interface for FitFindr. The layout and wiring are already set up —
your job is to fill in handle_query() so it calls run_agent() and maps
the session results to the three output panels.

Run with:
    python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860,
but check your terminal — the port may differ).
"""

import gradio as gr

from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── query handler ─────────────────────────────────────────────────────────────

def handle_query(user_query: str, wardrobe_choice: str) -> tuple[str, str, str, str, str, str]:
    """
    Called by Gradio when the user submits a query.

    Args:
        user_query:     The text the user typed into the search box.
        wardrobe_choice: Either "Example wardrobe" or "Empty wardrobe (new user)".

    Returns:
        A tuple of six strings:
            (listing_text, outfit_suggestion, fit_card, price_comparison, trend_insight, profile_summary)
    """
    # Step 1: Guard against an empty query
    if not user_query or not user_query.strip():
        return "Please enter a search query — describe what you're looking for.", "", "", "", "", ""

    # Step 2: Select the wardrobe based on wardrobe_choice
    if wardrobe_choice == "Empty wardrobe (new user)":
        wardrobe = get_empty_wardrobe()
    else:
        wardrobe = get_example_wardrobe()

    # Step 3: Call run_agent() with the query and selected wardrobe
    session = run_agent(user_query, wardrobe)

    # Step 4: If session["error"] is set, return the error in the first panel
    if session["error"]:
        return session["error"], "", "", "", "", ""

    # Step 5: Format selected_item into a readable listing_text string
    item = session["selected_item"]
    if item:
        listing_text = (
            f"**{item['title']}**\n\n"
            f"💰 ${item['price']:.2f}  |  📍 {item['platform']}\n"
            f"📏 Size: {item['size']}  |  📦 Condition: {item['condition']}\n"
            f"🏷️  {', '.join(item['style_tags'])}\n"
            f"🎨 Colors: {', '.join(item['colors'])}\n"
            f"🏷️  Brand: {item.get('brand') or 'Unbranded'}\n\n"
            f"{item['description']}"
        )
        # If retry adjustments were made, prepend a note
        if session.get("retry_adjustments"):
            listing_text = (
                f"⚠️  **{session['retry_adjustments']}**\n\n{listing_text}"
            )
    else:
        listing_text = "No listing selected."

    return (
        listing_text,
        session["outfit_suggestion"] or "",
        session["fit_card"] or "",
        session.get("price_comparison") or "",
        session.get("trend_insight") or "",
        session.get("profile_summary") or "",
    )


# ── interface ─────────────────────────────────────────────────────────────────

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots size 8",
    "designer ballgown size XXS under $5",   # deliberate no-results test
]

def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas based on your wardrobe.
Describe what you're looking for — include size and price if you want to filter.
        """)

        with gr.Row():
            query_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee under $30, size M",
                lines=2,
                scale=3,
            )
            wardrobe_choice = gr.Radio(
                choices=["Example wardrobe", "Empty wardrobe (new user)"],
                value="Example wardrobe",
                label="Wardrobe",
                scale=1,
            )

        submit_btn = gr.Button("Find it", variant="primary")

        with gr.Row():
            listing_output = gr.Textbox(
                label="🛍️ Top listing found",
                lines=8,
                interactive=False,
            )
            outfit_output = gr.Textbox(
                label="👗 Outfit idea",
                lines=8,
                interactive=False,
            )
            fitcard_output = gr.Textbox(
                label="✨ Your fit card",
                lines=8,
                interactive=False,
            )

        with gr.Row():
            price_output = gr.Textbox(
                label="💵 Price check",
                lines=4,
                interactive=False,
            )
            trend_output = gr.Textbox(
                label="📈 Trend check",
                lines=4,
                interactive=False,
            )
            profile_output = gr.Textbox(
                label="🧠 Style profile",
                lines=4,
                interactive=False,
            )

        gr.Examples(
            examples=[[q, "Example wardrobe"] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice],
            label="Try these queries",
        )

        submit_btn.click(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output, price_output, trend_output, profile_output],
        )
        query_input.submit(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output, price_output, trend_output, profile_output],
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()

"""Generate a synthetic *stress* corpus for the fidelity harness.

Real-world PDFs (which only the maintainer can supply) remain the gold
standard. This generator produces varied, deterministic stress cases so the
harness and tuning can run *now* — borderless and gridlined tables, multi-
column layouts, mixed text+image, and dense multi-section pages.

Usage:  python -m tests.fidelity.gen_corpus     # writes into ./corpus
"""
from __future__ import annotations

import os
import fitz

OUT = os.path.join(os.path.dirname(__file__), "corpus")
PREFIX = "syn_"  # so these are easy to distinguish/remove from real PDFs


def _save(doc, name):
    path = os.path.join(OUT, PREFIX + name)
    doc.save(path); doc.close(); print("wrote", os.path.basename(path))


def gridlined_table():
    doc = fitz.open(); p = doc.new_page()
    p.insert_text((72, 60), "Gridlined Table Report", fontsize=16)
    rows = [("Item", "Qty", "Price"), ("Widget", "42", "$3.50"),
            ("Gadget", "7", "$12.00"), ("Sprocket", "128", "$0.75")]
    x0, y0, rh, cw = 72, 90, 28, 150
    for r in range(len(rows) + 1):
        p.draw_line((x0, y0 + r * rh), (x0 + cw * 3, y0 + r * rh))
    for c in range(4):
        p.draw_line((x0 + c * cw, y0), (x0 + c * cw, y0 + rh * len(rows)))
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            p.insert_text((x0 + c * cw + 8, y0 + r * rh + 18), val, fontsize=11)
    _save(doc, "table_gridlined.pdf")


def borderless_table():
    doc = fitz.open(); p = doc.new_page()
    p.insert_text((72, 60), "Borderless Table columns by alignment only", fontsize=14)
    rows = [("Region", "Q1", "Q2", "Q3"), ("North", "120", "134", "150"),
            ("South", "98", "102", "119"), ("East", "77", "88", "91")]
    x0, y0, rh, cols = 72, 100, 26, [0, 160, 260, 360]
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            p.insert_text((x0 + cols[c], y0 + r * rh), val, fontsize=11)
    _save(doc, "table_borderless.pdf")


def two_column():
    doc = fitz.open(); p = doc.new_page(); w = p.rect.width
    p.insert_textbox(fitz.Rect(50, 50, w - 50, 80), "Two-Column Newsletter",
                     fontsize=18, align=fitz.TEXT_ALIGN_CENTER)
    left = ("Operating expenses stayed flat quarter over quarter while headcount "
            "grew eight percent reflecting tighter vendor management and lower "
            "cloud spend across the platform teams this period overall.")
    right = ("Customer satisfaction climbed to ninety four percent the highest "
             "recorded driven by faster support response times and the new "
             "onboarding flow that shipped at the start of the quarter.")
    p.insert_textbox(fitz.Rect(50, 110, w / 2 - 15, 320), left, fontsize=10)
    p.insert_textbox(fitz.Rect(w / 2 + 15, 110, w - 50, 320), right, fontsize=10)
    _save(doc, "twocol.pdf")


def three_column():
    doc = fitz.open(); p = doc.new_page(); w = p.rect.width
    p.insert_textbox(fitz.Rect(40, 40, w - 40, 70), "Three-Column Brochure",
                     fontsize=16, align=fitz.TEXT_ALIGN_CENTER)
    body = ("Column body text with several sentences of real extractable words "
            "so the retention metric has something meaningful to measure here.")
    cw = (w - 80) / 3
    for i in range(3):
        x = 40 + i * cw
        p.insert_textbox(fitz.Rect(x + 4, 90, x + cw - 4, 320), body, fontsize=9)
    _save(doc, "threecol.pdf")


def mixed_text_image():
    doc = fitz.open(); p = doc.new_page()
    p.insert_text((72, 60), "Mixed Text and Image", fontsize=16)
    p.insert_textbox(fitz.Rect(72, 90, 520, 200),
                     ("Introductory paragraph explaining the figure below with "
                      "enough words to score text retention properly here."), fontsize=11)
    p.draw_rect(fitz.Rect(72, 220, 320, 380), color=(0.2, 0.4, 0.8), fill=(0.8, 0.9, 1.0))
    p.insert_text((90, 300), "Figure 1", fontsize=12)
    p.insert_textbox(fitz.Rect(72, 400, 520, 500),
                     "Closing paragraph after the figure with more real words.", fontsize=11)
    _save(doc, "mixed.pdf")


def dense_multisection():
    doc = fitz.open(); p = doc.new_page(); y = 60
    for s in range(1, 5):
        p.insert_text((72, y), f"Section {s} Heading", fontsize=13); y += 22
        p.insert_textbox(fitz.Rect(72, y, 520, y + 90),
                         (f"Section {s} body paragraph one with substantive text "
                          "content for the retention metric to evaluate. ") * 2, fontsize=10)
        y += 100
    _save(doc, "dense.pdf")


def main():
    os.makedirs(OUT, exist_ok=True)
    gridlined_table(); borderless_table(); two_column()
    three_column(); mixed_text_image(); dense_multisection()


if __name__ == "__main__":
    main()

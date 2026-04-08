#!/usr/bin/env python3
"""
LinkedIn Carousel PDF Generator for RuleDSL product post.

Generates a 6-slide PDF optimized for LinkedIn carousel format (1080x1080px).
Each slide is a self-contained page with code snippets and minimal text.

Usage:
    pip install reportlab
    python generate_slides.py              # outputs linkedin_carousel.pdf
    python generate_slides.py -o custom.pdf
"""

import argparse
import sys
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

# LinkedIn carousel optimal: 1080x1080 px → we use mm equivalent at 72 dpi
SLIDE_W = 190 * mm
SLIDE_H = 190 * mm

# Colors — dark theme (developer-friendly)
BG_DARK = HexColor("#0f1117")
BG_CODE = HexColor("#1a1d27")
TEXT_WHITE = HexColor("#e6edf3")
TEXT_DIM = HexColor("#8b949e")
ACCENT_GREEN = HexColor("#3fb950")
ACCENT_BLUE = HexColor("#58a6ff")
ACCENT_ORANGE = HexColor("#d29922")
ACCENT_PURPLE = HexColor("#bc8cff")
ACCENT_RED = HexColor("#f85149")
KEYWORD_PINK = HexColor("#ff7b72")

# Fonts
FONT_MONO = "Courier"
FONT_MONO_BOLD = "Courier-Bold"
FONT_SANS = "Helvetica"
FONT_SANS_BOLD = "Helvetica-Bold"


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def draw_bg(c):
    """Fill entire slide with dark background."""
    c.setFillColor(BG_DARK)
    c.rect(0, 0, SLIDE_W, SLIDE_H, fill=True, stroke=False)


def draw_code_block(c, x, y, w, h, radius=4 * mm):
    """Draw a rounded rectangle code background."""
    c.setFillColor(BG_CODE)
    c.roundRect(x, y, w, h, radius, fill=True, stroke=False)


def draw_dot_bar(c, x, y):
    """Draw macOS-style window dots."""
    colors = [HexColor("#ff5f57"), HexColor("#febc2e"), HexColor("#28c840")]
    for i, col in enumerate(colors):
        c.setFillColor(col)
        c.circle(x + i * 5.5 * mm, y, 1.8 * mm, fill=True, stroke=False)


def draw_text(c, x, y, text, font=FONT_SANS, size=12, color=TEXT_WHITE):
    """Draw a single line of text."""
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawString(x, y, text)


def draw_text_centered(c, y, text, font=FONT_SANS_BOLD, size=18, color=TEXT_WHITE):
    """Draw centered text."""
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawCentredString(SLIDE_W / 2, y, text)


def draw_code_lines(c, x, y, lines, size=11, line_height=5.5 * mm):
    """
    Draw syntax-highlighted code lines.
    Each line is a list of (text, color) tuples.
    """
    for i, line_parts in enumerate(lines):
        cx = x
        cy = y - i * line_height
        for text, color in line_parts:
            c.setFont(FONT_MONO, size)
            c.setFillColor(color)
            c.drawString(cx, cy, text)
            cx += c.stringWidth(text, FONT_MONO, size)


def draw_slide_number(c, num, total=6):
    """Draw slide number indicator at bottom."""
    c.setFont(FONT_SANS, 8)
    c.setFillColor(TEXT_DIM)
    c.drawCentredString(SLIDE_W / 2, 6 * mm, f"{num} / {total}")


def draw_branding(c, y=12 * mm):
    """Draw RuleDSL branding at bottom."""
    c.setFont(FONT_SANS, 8)
    c.setFillColor(TEXT_DIM)
    c.drawCentredString(SLIDE_W / 2, y, "ruledsl.dev")


# ---------------------------------------------------------------------------
# Slide definitions
# ---------------------------------------------------------------------------

def slide_1_hook(c):
    """Slide 1: Hook — headline + tagline."""
    draw_bg(c)

    # Main headline
    draw_text_centered(c, SLIDE_H * 0.62, "Same input.", FONT_SANS_BOLD, 28, TEXT_WHITE)
    draw_text_centered(c, SLIDE_H * 0.54, "Same output.", FONT_SANS_BOLD, 28, TEXT_WHITE)
    draw_text_centered(c, SLIDE_H * 0.46, "Every time.", FONT_SANS_BOLD, 28, ACCENT_GREEN)

    # Divider line
    c.setStrokeColor(HexColor("#30363d"))
    c.setLineWidth(0.5)
    c.line(SLIDE_W * 0.3, SLIDE_H * 0.38, SLIDE_W * 0.7, SLIDE_H * 0.38)

    # Subtitle
    draw_text_centered(c, SLIDE_H * 0.32, "RuleDSL", FONT_SANS_BOLD, 20, ACCENT_BLUE)
    draw_text_centered(c, SLIDE_H * 0.26,
                       "Deterministic Business Rule Engine",
                       FONT_SANS, 13, TEXT_DIM)

    draw_slide_number(c, 1)


def slide_2_rule(c):
    """Slide 2: Rule definition — show the DSL syntax."""
    draw_bg(c)

    draw_text_centered(c, SLIDE_H * 0.88, "1. Write a rule", FONT_SANS_BOLD, 16, TEXT_DIM)

    # Code block
    bx, by, bw, bh = 14 * mm, SLIDE_H * 0.18, SLIDE_W - 28 * mm, SLIDE_H * 0.62
    draw_code_block(c, bx, by, bw, bh)
    draw_dot_bar(c, bx + 6 * mm, by + bh - 6 * mm)

    # File label
    draw_text(c, bx + 24 * mm, by + bh - 7.5 * mm, "risk.rule", FONT_MONO, 8, TEXT_DIM)

    # Code
    code_x = bx + 8 * mm
    code_y = by + bh - 20 * mm
    lh = 6 * mm

    lines = [
        [("RULE", KEYWORD_PINK), (" high_risk {", TEXT_WHITE)],
        [("  WHEN ", KEYWORD_PINK), ("amount > 1000", TEXT_WHITE)],
        [("   AND ", KEYWORD_PINK), ("currency == ", TEXT_WHITE),
         ('"USD"', ACCENT_GREEN), (";", TEXT_WHITE)],
        [("  THEN ", KEYWORD_PINK), ("DECLINE", ACCENT_RED), (";", TEXT_WHITE)],
        [("}", TEXT_WHITE)],
        [],
        [("RULE", KEYWORD_PINK), (" default_allow {", TEXT_WHITE)],
        [("  WHEN ", KEYWORD_PINK), ("amount > 0", TEXT_WHITE), (";", TEXT_WHITE)],
        [("  THEN ", KEYWORD_PINK), ("ALLOW", ACCENT_GREEN), (";", TEXT_WHITE)],
        [("}", TEXT_WHITE)],
    ]

    draw_code_lines(c, code_x, code_y, lines, size=12, line_height=lh)

    # Bottom note
    draw_text_centered(c, SLIDE_H * 0.10,
                       "Human-readable. Auditable. Deterministic.",
                       FONT_SANS, 11, TEXT_DIM)

    draw_slide_number(c, 2)


def slide_3_compile(c):
    """Slide 3: Compile to bytecode — CLI step."""
    draw_bg(c)

    draw_text_centered(c, SLIDE_H * 0.88, "2. Compile to bytecode", FONT_SANS_BOLD, 16, TEXT_DIM)

    # Terminal block
    bx, by, bw, bh = 14 * mm, SLIDE_H * 0.38, SLIDE_W - 28 * mm, SLIDE_H * 0.40
    draw_code_block(c, bx, by, bw, bh)
    draw_dot_bar(c, bx + 6 * mm, by + bh - 6 * mm)
    draw_text(c, bx + 24 * mm, by + bh - 7.5 * mm, "terminal", FONT_MONO, 8, TEXT_DIM)

    code_x = bx + 8 * mm
    code_y = by + bh - 22 * mm

    lines = [
        [("$ ", TEXT_DIM), ("ruledslc compile", ACCENT_BLUE),
         (" risk.rule", TEXT_WHITE)],
        [("  ", TEXT_WHITE), ("-o risk.axbc", TEXT_DIM)],
        [],
        [("Compiled OK", ACCENT_GREEN), (" — 148 bytes", TEXT_DIM)],
        [("Language: ", TEXT_DIM), ("v1.0", TEXT_WHITE)],
        [("Target:   ", TEXT_DIM), ("axbc3", TEXT_WHITE)],
    ]

    draw_code_lines(c, code_x, code_y, lines, size=11, line_height=6 * mm)

    # Explanation
    draw_text_centered(c, SLIDE_H * 0.28,
                       "Offline compilation. Ship bytecode, not source.",
                       FONT_SANS, 11, TEXT_DIM)

    # Visual: .rule → .axbc
    arrow_y = SLIDE_H * 0.18
    draw_text(c, SLIDE_W * 0.15, arrow_y, "risk.rule", FONT_MONO_BOLD, 14, TEXT_WHITE)

    # Draw arrow using canvas line + triangle
    ax1 = SLIDE_W * 0.40
    ax2 = SLIDE_W * 0.56
    ay = arrow_y + 3.5
    c.setStrokeColor(ACCENT_BLUE)
    c.setLineWidth(2)
    c.line(ax1, ay, ax2 - 3 * mm, ay)
    # Arrowhead
    c.setFillColor(ACCENT_BLUE)
    arrow_path = c.beginPath()
    arrow_path.moveTo(ax2, ay)
    arrow_path.lineTo(ax2 - 4 * mm, ay + 2.5 * mm)
    arrow_path.lineTo(ax2 - 4 * mm, ay - 2.5 * mm)
    arrow_path.close()
    c.drawPath(arrow_path, fill=True, stroke=False)

    draw_text(c, SLIDE_W * 0.60, arrow_y, "risk.axbc", FONT_MONO_BOLD, 14, ACCENT_GREEN)

    draw_slide_number(c, 3)


def slide_4_python(c):
    """Slide 4: Python evaluation code."""
    draw_bg(c)

    draw_text_centered(c, SLIDE_H * 0.88, "3. Evaluate in Python", FONT_SANS_BOLD, 16, TEXT_DIM)

    # Code block
    bx, by, bw, bh = 14 * mm, SLIDE_H * 0.15, SLIDE_W - 28 * mm, SLIDE_H * 0.66
    draw_code_block(c, bx, by, bw, bh)
    draw_dot_bar(c, bx + 6 * mm, by + bh - 6 * mm)
    draw_text(c, bx + 24 * mm, by + bh - 7.5 * mm, "evaluate.py", FONT_MONO, 8, TEXT_DIM)

    code_x = bx + 8 * mm
    code_y = by + bh - 20 * mm
    lh = 5.8 * mm

    lines = [
        [("from ", KEYWORD_PINK), ("ruledsl ", TEXT_WHITE),
         ("import ", KEYWORD_PINK), ("RuleDSL", ACCENT_BLUE)],
        [],
        [("engine = ", TEXT_WHITE), ("RuleDSL", ACCENT_BLUE),
         ("(", TEXT_WHITE), ('"ruledsl_capi.so"', ACCENT_GREEN), (")", TEXT_WHITE)],
        [],
        [("bc = engine.compile(", TEXT_WHITE)],
        [('  open(', TEXT_WHITE), ('"risk.rule"', ACCENT_GREEN),
         (').read()', TEXT_WHITE)],
        [(")", TEXT_WHITE)],
        [],
        [("decision = engine.evaluate(bc, {", TEXT_WHITE)],
        [('    "amount"', ACCENT_GREEN), (":  ", TEXT_WHITE),
         ("1200.0", ACCENT_ORANGE), (",", TEXT_WHITE)],
        [('    "currency"', ACCENT_GREEN), (": ", TEXT_WHITE),
         ('"USD"', ACCENT_GREEN), (",", TEXT_WHITE)],
        [("}", TEXT_WHITE), (")", TEXT_WHITE)],
    ]

    draw_code_lines(c, code_x, code_y, lines, size=10.5, line_height=lh)

    draw_slide_number(c, 4)


def slide_5_output(c):
    """Slide 5: Decision output — the punchline."""
    draw_bg(c)

    draw_text_centered(c, SLIDE_H * 0.88, "4. Get the decision", FONT_SANS_BOLD, 16, TEXT_DIM)

    # Output block
    bx, by, bw, bh = 14 * mm, SLIDE_H * 0.42, SLIDE_W - 28 * mm, SLIDE_H * 0.36
    draw_code_block(c, bx, by, bw, bh)
    draw_dot_bar(c, bx + 6 * mm, by + bh - 6 * mm)

    code_x = bx + 8 * mm
    code_y = by + bh - 22 * mm

    lines = [
        [(">>> ", TEXT_DIM), ("decision.action", TEXT_WHITE)],
        [('"DECLINE"', ACCENT_RED)],
        [],
        [(">>> ", TEXT_DIM), ("decision.rule_name", TEXT_WHITE)],
        [('"high_risk"', ACCENT_ORANGE)],
        [],
        [(">>> ", TEXT_DIM), ("decision.matched", TEXT_WHITE)],
        [("True", ACCENT_GREEN)],
    ]

    draw_code_lines(c, code_x, code_y, lines, size=13, line_height=6.5 * mm)

    # Bottom emphasis
    draw_text_centered(c, SLIDE_H * 0.28,
                       "Deterministic. Reproducible. Auditable.",
                       FONT_SANS_BOLD, 14, ACCENT_GREEN)
    draw_text_centered(c, SLIDE_H * 0.20,
                       "Run it again tomorrow — same result.",
                       FONT_SANS, 11, TEXT_DIM)

    draw_slide_number(c, 5)


def slide_6_cta(c):
    """Slide 6: Closing — value props + CTA."""
    draw_bg(c)

    # Title
    draw_text_centered(c, SLIDE_H * 0.80, "RuleDSL", FONT_SANS_BOLD, 28, ACCENT_BLUE)
    draw_text_centered(c, SLIDE_H * 0.73,
                       "Deterministic Business Rule Engine",
                       FONT_SANS, 13, TEXT_DIM)

    # Value props
    props = [
        ("No service dependency", "In-process C ABI — embed anywhere"),
        ("No database required", "Bytecode in, decision out"),
        ("No surprises", "Same input → same output, guaranteed"),
        ("Any language", "Python, C, C#, Go — anything with FFI"),
    ]

    y = SLIDE_H * 0.60
    for title, desc in props:
        # Checkmark
        draw_text(c, SLIDE_W * 0.12, y, "✓", FONT_SANS_BOLD, 14, ACCENT_GREEN)
        draw_text(c, SLIDE_W * 0.17, y, title, FONT_SANS_BOLD, 12, TEXT_WHITE)
        draw_text(c, SLIDE_W * 0.17, y - 4.5 * mm, desc, FONT_SANS, 9.5, TEXT_DIM)
        y -= 14 * mm

    # Divider
    c.setStrokeColor(HexColor("#30363d"))
    c.setLineWidth(0.5)
    c.line(SLIDE_W * 0.2, SLIDE_H * 0.14, SLIDE_W * 0.8, SLIDE_H * 0.14)

    # CTA
    draw_text_centered(c, SLIDE_H * 0.08, "DM for early access", FONT_SANS_BOLD, 13, TEXT_WHITE)

    draw_slide_number(c, 6)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SLIDES = [
    slide_1_hook,
    slide_2_rule,
    slide_3_compile,
    slide_4_python,
    slide_5_output,
    slide_6_cta,
]


def generate(output_path: str):
    c = Canvas(output_path, pagesize=(SLIDE_W, SLIDE_H))

    for i, slide_fn in enumerate(SLIDES):
        slide_fn(c)
        if i < len(SLIDES) - 1:
            c.showPage()

    c.save()
    print(f"Generated {len(SLIDES)} slides → {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate LinkedIn carousel PDF for RuleDSL")
    parser.add_argument("-o", "--output", default="linkedin_carousel.pdf",
                        help="Output PDF path (default: linkedin_carousel.pdf)")
    args = parser.parse_args()
    generate(args.output)


if __name__ == "__main__":
    main()

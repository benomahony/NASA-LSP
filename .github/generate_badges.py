#!/usr/bin/env python3
"""Generate SVG badges for coverage and mutation testing."""
# ruff: noqa: T201, PLR2004

import sys
from pathlib import Path


def generate_badge_svg(label: str, value: str, color: str) -> str:
    """Generate an SVG badge."""
    # Calculate widths
    label_width = len(label) * 7 + 10
    value_width = len(value) * 7 + 10
    total_width = label_width + value_width

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20">
  <linearGradient id="b" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <mask id="a">
    <rect width="{total_width}" height="20" rx="3" fill="#fff"/>
  </mask>
  <g mask="url(#a)">
    <path fill="#555" d="M0 0h{label_width}v20H0z"/>
    <path fill="{color}" d="M{label_width} 0h{value_width}v20H{label_width}z"/>
    <path fill="url(#b)" d="M0 0h{total_width}v20H0z"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="{label_width / 2}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{label_width / 2}" y="14">{label}</text>
    <text x="{label_width + value_width / 2}" y="15" fill="#010101" fill-opacity=".3">{value}</text>
    <text x="{label_width + value_width / 2}" y="14">{value}</text>
  </g>
</svg>"""


def get_color_for_coverage(percentage: float) -> str:
    """Get color based on coverage percentage."""
    if percentage >= 90:
        return "#4c1"
    if percentage >= 75:
        return "#97ca00"
    if percentage >= 60:
        return "#dfb317"
    return "#e05d44"


def get_color_for_mutation(percentage: float) -> str:
    """Get color based on mutation score."""
    if percentage >= 80:
        return "#4c1"
    if percentage >= 60:
        return "#97ca00"
    if percentage >= 40:
        return "#dfb317"
    return "#e05d44"


def main() -> None:
    """Generate badge SVG files."""
    if len(sys.argv) != 3:
        print("Usage: generate_badges.py <coverage_percentage> <mutation_score>")
        sys.exit(1)

    coverage_pct = float(sys.argv[1])
    mutation_pct = float(sys.argv[2])

    badges_dir = Path(".github/badges")
    badges_dir.mkdir(parents=True, exist_ok=True)

    # Generate coverage badge
    coverage_color = get_color_for_coverage(coverage_pct)
    coverage_svg = generate_badge_svg("coverage", f"{coverage_pct:.0f}%", coverage_color)
    (badges_dir / "coverage.svg").write_text(coverage_svg)

    # Generate mutation badge
    mutation_color = get_color_for_mutation(mutation_pct)
    mutation_svg = generate_badge_svg("mutation", f"{mutation_pct:.0f}%", mutation_color)
    (badges_dir / "mutation.svg").write_text(mutation_svg)

    print(f"Generated badges: coverage={coverage_pct:.0f}%, mutation={mutation_pct:.0f}%")


if __name__ == "__main__":
    main()

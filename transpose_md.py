"""Transpose markdown hierarchy: swap H1 and H2 levels.

Given a markdown file where H1s represent one grouping (e.g. roles) and H2s
represent another (e.g. phases), this script flips the hierarchy so that
H2s become H1s and vice versa, preserving all content.
"""

import sys
from collections import OrderedDict
from pathlib import Path


def parse_md(lines: list[str]) -> OrderedDict[str, OrderedDict[str, list[str]]]:
    """Parse markdown into {h1: {h2: [content_lines]}} preserving order."""
    result: OrderedDict[str, OrderedDict[str, list[str]]] = OrderedDict()
    current_h1 = None
    current_h2 = None

    for line in lines:
        if line.startswith("# "):
            current_h1 = line[2:].strip()
            current_h2 = None
            if current_h1 not in result:
                result[current_h1] = OrderedDict()
        elif line.startswith("## ") and current_h1 is not None:
            current_h2 = line[3:].strip()
            if current_h2 not in result[current_h1]:
                result[current_h1][current_h2] = []
        elif current_h1 is not None and current_h2 is not None:
            result[current_h1][current_h2].append(line)

    return result


def transpose(data: OrderedDict[str, OrderedDict[str, list[str]]]) -> OrderedDict[str, OrderedDict[str, list[str]]]:
    """Transpose {h1: {h2: content}} to {h2: {h1: content}}, preserving first-seen order."""
    phase_order: list[str] = []
    for h2s in data.values():
        for h2 in h2s:
            if h2 not in phase_order:
                phase_order.append(h2)

    result: OrderedDict[str, OrderedDict[str, list[str]]] = OrderedDict()
    for phase in phase_order:
        result[phase] = OrderedDict()
        for h1, h2s in data.items():
            if phase in h2s:
                result[phase][h1] = h2s[phase]

    return result


def render_md(data: OrderedDict[str, OrderedDict[str, list[str]]]) -> str:
    """Render transposed structure back to markdown."""
    sections = []
    for h1, h2s in data.items():
        lines = [f"# {h1}\n"]
        for h2, content in h2s.items():
            lines.append(f"## {h2}\n")
            # Strip leading/trailing blank lines from content, then add one trailing blank
            stripped = content
            while stripped and stripped[0].strip() == "":
                stripped = stripped[1:]
            while stripped and stripped[-1].strip() == "":
                stripped = stripped[:-1]
            lines.extend(stripped)
            lines.append("")
        sections.append("\n".join(lines))

    return "\n\n".join(sections) + "\n"


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} input.md [output.md]", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = input_path.with_stem(input_path.stem + "_transposed")

    lines = input_path.read_text().splitlines()
    data = parse_md(lines)
    transposed = transpose(data)
    output_path.write_text(render_md(transposed))
    print(f"Wrote transposed markdown to {output_path}")


if __name__ == "__main__":
    main()

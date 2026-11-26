"""Render docs/BRIEF.md to a print-ready A4 HTML page (standard library only).

    python tools/brief/build_brief.py            # writes out/brief/brief.html
    msedge --headless --print-to-pdf=docs/brief.pdf out/brief/brief.html

Supports the Markdown the brief uses: headings, paragraphs, bullet lists, pipe tables, fenced
code blocks, **bold**, `code` and bare links.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSS = """
@page { size: A4; margin: 11mm 13mm; }
body { font-family: "Segoe UI", Arial, sans-serif; font-size: 10pt; line-height: 1.28; color: #111; }
h1 { font-size: 14pt; margin: 0 0 2pt; }
h2 { font-size: 11pt; margin: 7pt 0 2pt; border-bottom: 1px solid #999; }
p { margin: 2pt 0 3pt; }
ul { margin: 2pt 0 3pt 14pt; padding: 0; }
li { margin: 0 0 1.5pt; }
table { border-collapse: collapse; width: 100%; margin: 3pt 0; }
td, th { border: 1px solid #aaa; padding: 1.5pt 4pt; vertical-align: top; font-size: 10pt; }
th { background: #eee; text-align: left; }
pre { font-family: Consolas, monospace; font-size: 7.6pt; line-height: 1.15; background: #f4f4f4;
      padding: 3pt; margin: 3pt 0; white-space: pre; overflow: hidden; }
code { font-family: Consolas, monospace; font-size: 9pt; }
"""


def inline(text: str) -> str:
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(f"<code>{html.escape(part[1:-1])}</code>")
            continue
        s = html.escape(part)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(https://[^\s<]+)", r'<a href="\1">\1</a>', s)
        out.append(s)
    return "".join(out)


def render(md: str) -> str:
    lines = md.splitlines()
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            out.append("<pre>" + html.escape("\n".join(lines[i + 1:j])) + "</pre>")
            i = j + 1
        elif line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{level}>{inline(line[level:].strip())}</h{level}>")
            i += 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            head, body = rows[0], rows[1:]
            out.append("<table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
                       + "</table>")
        elif line.startswith("- "):
            items = []
            while i < len(lines) and (lines[i].startswith("- ") or lines[i].startswith("  ")):
                if lines[i].startswith("- "):
                    items.append(lines[i][2:].strip())
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
        elif not line.strip():
            i += 1
        else:
            para = [line.strip()]
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|", "- ", "```")):
                para.append(lines[i].strip())
                i += 1
            out.append(f"<p>{inline(' '.join(para))}</p>")
    return "\n".join(out)


def main() -> int:
    src = ROOT / "docs" / "BRIEF.md"
    dest = ROOT / "out" / "brief" / "brief.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = render(src.read_text(encoding="utf-8"))
    dest.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head>'
                    f"<body>{body}</body></html>\n", encoding="utf-8")
    print(dest.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())

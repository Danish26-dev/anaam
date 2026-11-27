"""Render docs/BRIEF.md to a print-ready A4 page and, with --pdf, to docs/brief.pdf.

    python tools/brief/build_brief.py          # writes out/brief/brief.html
    python tools/brief/build_brief.py --pdf    # also prints docs/brief.pdf with headless Edge/Chrome

Standard library only. Supports the Markdown the brief uses: headings, paragraphs, bullet lists,
pipe tables, fenced code blocks, **bold**, *italic*, `code`, bare links, images on their own line
(`![caption](path)`, used for the SVG diagrams) and `<!-- pagebreak -->`.
The kit requires 2 A4 pages at 10 pt or larger, so body text, tables and code are 10 pt.
"""
from __future__ import annotations

import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"

CSS = """
@page { size: A4; margin: 9mm 11mm 9mm 11mm; }
* { box-sizing: border-box; }
body { font-family: "Segoe UI", Arial, sans-serif; font-size: 10pt; line-height: 1.24; color: #16201d; margin: 0; }
h1 { font-size: 15pt; margin: 0 0 1pt; color: #204B42; }
h2 { font-size: 11pt; margin: 5pt 0 2pt; padding-bottom: 1pt; border-bottom: 1.2px solid #204B42; color: #204B42; }
p { margin: 1.5pt 0 2.5pt; }
ul { margin: 1pt 0 2pt 12pt; padding: 0; }
li { margin: 0 0 1.6pt; }
table { border-collapse: collapse; width: 100%; margin: 2pt 0 3pt; }
td, th { border: 1px solid #b9c3bd; padding: 1.2pt 4pt; vertical-align: top; font-size: 10pt; }
th { background: #e8eeea; text-align: left; }
td:first-child { width: 22%; font-weight: 600; }
tr, li { break-inside: avoid; }
h2 { break-after: avoid; }
pre { font-family: Consolas, monospace; font-size: 10pt; background: #f4f4f4; padding: 3pt; margin: 3pt 0; white-space: pre-wrap; }
code { font-family: Consolas, monospace; font-size: 10pt; }
a { color: #204B42; }
figure { margin: 2pt 0 4pt; break-inside: avoid; }
figure img { width: 100%; display: block; }
figcaption { font-size: 10pt; font-weight: 600; margin: 0 0 2pt; color: #204B42; }
.pagebreak { break-before: page; }
"""


def inline(text: str) -> str:
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(f"<code>{html.escape(part[1:-1])}</code>")
            continue
        s = html.escape(part, quote=False)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
        s = re.sub(r"(https://[^\s<)]+)", r'<a href="\1">\1</a>', s)
        out.append(s)
    return "".join(out)


IMAGE = re.compile(r"^!\[(.*)\]\(([^)]+)\)\s*$")


def render(md: str, base: Path) -> str:
    lines = md.splitlines()
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        m = IMAGE.match(line.strip())
        if line.strip() == "<!-- pagebreak -->":
            out.append('<div class="pagebreak"></div>')
            i += 1
        elif m:
            src = (base / m.group(2)).resolve().as_uri()
            out.append(f'<figure><figcaption>{inline(m.group(1))}</figcaption>'
                       f'<img src="{src}" alt="{html.escape(m.group(1))}"></figure>')
            i += 1
        elif line.startswith("```"):
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
        elif not line.strip() or line.strip().startswith("<!--"):
            i += 1
        else:
            para = [line.strip()]
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|", "- ", "```", "![", "<!--")):
                para.append(lines[i].strip())
                i += 1
            out.append(f"<p>{inline(' '.join(para))}</p>")
    return "\n".join(out)


def find_browser() -> str | None:
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]
    for c in candidates:
        if Path(c).is_file():
            return c
    for name in ("msedge", "microsoft-edge", "google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    return None


def main() -> int:
    src = DOCS / "BRIEF.md"
    dest = ROOT / "out" / "brief" / "brief.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = render(src.read_text(encoding="utf-8"), src.parent)
    dest.write_text(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Anaam project brief</title>'
                    f"<style>{CSS}</style></head><body>{body}</body></html>\n", encoding="utf-8")
    print(dest.relative_to(ROOT).as_posix())
    if "--pdf" in sys.argv:
        browser = find_browser()
        if not browser:
            print("ERROR no Edge/Chrome found for --pdf", file=sys.stderr)
            return 1
        pdf = DOCS / "brief.pdf"
        subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        "--allow-file-access-from-files", f"--print-to-pdf={pdf}", dest.as_uri()],
                       check=True, capture_output=True, timeout=120)
        pages = len(re.findall(rb"/Type\s*/Page(?!s)", pdf.read_bytes()))
        print(f"{pdf.relative_to(ROOT).as_posix()} pages={pages}")
        if pages > 2:
            print("WARNING the kit reads only the first 2 pages", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

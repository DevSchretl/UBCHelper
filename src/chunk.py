"""
Chunk — turn one cached page into a list of retrieval-sized document records.

Calendar pages are long and heterogeneous (unlike a recipe), so one-page-one-document does
not carry over. Each page's MAIN content (`#primary-content` — never the giant sidebar nav) is
converted to markdown-ish text with requirement tables preserved, split into sections on
headings, and capped to ~config.CHUNK_MAX_CHARS. The disambiguators that naive RAG misses —
edition year and cohort qualifier (parsed from the page title/slug) — are folded into each
chunk's `title`/`text`, and also carried as structured metadata keys for the agent + eval.

Every emitted record follows the engine's contract (`text`/`title`/`url`/`section`, `id` added
later by ingest) plus extra metadata keys the engine ignores but preserves in metadata.json.

Quick check on the cached pages:
    python -m src.chunk                     # chunk everything in data/pages, print stats
    python -m src.chunk data/pages/live-2627/<hash>.json   # chunk one page, print it
"""

from __future__ import annotations

import json
import re
import sys

from bs4 import BeautifulSoup, Comment, NavigableString

from . import config

# Tags that carry block-level flow content; everything else is either inline or a wrapper.
# NOTE: <figure> is deliberately NOT here — Drupal's CKEditor wraps every requirement table in
# <figure class="table">, so we must descend through it to reach the <table>.
FLOW_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "table", "hr",
             "blockquote", "pre", "dl"}
SKIP_TAGS = {"script", "style", "noscript"}
SECTION_BOUNDARY = {"h2", "h3", "h4"}  # start a new chunk section at these headings

# Boilerplate that may nest inside the content region; stripped defensively (the sidebar nav
# is a SIBLING of #primary-content, so selecting the main region already drops it). The page
# <h1> and any in-content <nav> (breadcrumb/pager) are stripped too — after the breadcrumb and
# title have already been read from the untouched soup.
STRIP_SELECTORS = ("#sidebar-primary", "#block-shareblock", "#help-region",
                   "nav", "h1", "script", "style", "noscript")


# --------------------------------------------------------------------------------------
# Inline / block rendering (hand-rolled HTML -> markdown; deps stay requests+bs4+lxml only)
# --------------------------------------------------------------------------------------
def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def render_inline(node) -> str:
    if isinstance(node, Comment):  # Drupal Twig theme-debug comments — drop them
        return ""
    if isinstance(node, NavigableString):
        return _collapse(str(node))
    name = node.name
    if name == "br":
        return "\n"
    inner = "".join(render_inline(c) for c in node.children)
    stripped = inner.strip()
    if name == "sup":
        return "^" + stripped
    if name in ("strong", "b"):
        return f"**{stripped}**" if stripped else ""
    if name in ("em", "i"):
        return f"*{stripped}*" if stripped else ""
    # <a>: keep the anchor text only (clean for embeddings); cross-ref labels are meaningful.
    return inner


def _cell_text(cell) -> str:
    return render_inline(cell).replace("\n", " ").strip() or " "


def table_to_md(table) -> str:
    """Bare calendar tables have no <thead>/<th>; columns are positional. Preserve every row and
    cell in order (footnote `<sup>` markers and trailing colspan footnote rows included), and
    emit valid GFM by treating the first row as the header."""
    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"], recursive=False) or tr.find_all(["td", "th"])
        rows.append([_cell_text(c).replace("|", r"\|") for c in cells])
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return ""
    ncol = max(len(r) for r in rows)
    lines = []
    for i, r in enumerate(rows):
        r = r + [" "] * (ncol - len(r))
        lines.append("| " + " | ".join(r) + " |")
        if i == 0:
            lines.append("| " + " | ".join(["---"] * ncol) + " |")
    return "\n".join(lines)


def render_block(el) -> str:
    name = el.name
    if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return "#" * min(int(name[1]), 6) + " " + render_inline(el).strip()
    if name == "p":
        return render_inline(el).strip()
    if name in ("ul", "ol"):
        items = []
        for i, li in enumerate(el.find_all("li", recursive=False), 1):
            marker = "- " if name == "ul" else f"{i}. "
            items.append(marker + render_inline(li).strip())
        return "\n".join(items)
    if name == "hr":
        return "---"
    return render_inline(el).strip()


# --------------------------------------------------------------------------------------
# Flow extraction + sectioning
# --------------------------------------------------------------------------------------
_BLOCK_LIST_MARKERS = ("article", "h1", "h2", "h3", "h4", "h5", "h6", "table", "figure")


def _is_block_list(lst) -> bool:
    """True if a <ul>/<ol> holds block content (e.g. a Drupal View where each <li> is a full
    course <article> with its own heading), as opposed to a plain inline bullet list."""
    return lst.find(_BLOCK_LIST_MARKERS) is not None


def flow_elements(node) -> list[tuple[str, object]]:
    """Flatten the content region into an ordered list of ("el", tag) / ("text", string),
    descending through wrapper <div>/<section> so headings and tables come out in reading order."""
    out: list[tuple[str, object]] = []
    for child in node.children:
        if isinstance(child, Comment):  # Drupal Twig theme-debug comments — drop them
            continue
        if isinstance(child, NavigableString):
            if str(child).strip():
                out.append(("text", child))
        elif child.name in SKIP_TAGS:
            continue
        elif child.name in ("ul", "ol") and _is_block_list(child):
            out.extend(flow_elements(child))  # descend: items are articles/sections, not bullets
        elif child.name in FLOW_TAGS:
            out.append(("el", child))
        else:
            out.extend(flow_elements(child))
    return out


def split_sections(flow) -> list[dict]:
    sections: list[dict] = []
    current = {"heading": None, "elements": []}
    for kind, el in flow:
        if kind == "el" and el.name in SECTION_BOUNDARY:
            if current["elements"] or current["heading"]:
                sections.append(current)
            current = {"heading": _collapse(el.get_text(" ")).strip(), "elements": []}
        else:
            current["elements"].append((kind, el))
    if current["elements"] or current["heading"]:
        sections.append(current)
    return sections


def render_section(section) -> str:
    parts: list[str] = []
    for kind, el in section["elements"]:
        if kind == "text":
            t = _collapse(str(el)).strip()
            if t:
                parts.append(t)
        elif el.name == "table":
            md = table_to_md(el)
            if md:
                parts.append(md)
        else:
            md = render_block(el)
            if md.strip():
                parts.append(md.strip())
    return "\n\n".join(parts)


# --------------------------------------------------------------------------------------
# Chunking (size caps; tables never split)
# --------------------------------------------------------------------------------------
def _overlap_tail(text: str) -> str:
    tail = text[-config.CHUNK_OVERLAP:]
    if "|" in tail:  # don't carry a fragment of a table into the next chunk
        return ""
    i = tail.find(" ")
    return tail[i + 1:] if i != -1 else tail


def chunk_body(body_md: str) -> list[str]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", body_md) if b.strip()]
    chunks: list[str] = []
    cur = ""
    for b in blocks:
        is_table = b.lstrip().startswith("|")
        if is_table and len(b) > config.CHUNK_MAX_CHARS:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(b)  # oversized table kept whole
            continue
        if cur and len(cur) + len(b) + 2 > config.CHUNK_MAX_CHARS:
            chunks.append(cur)
            carry = _overlap_tail(cur)
            cur = (carry + "\n\n" + b).strip() if carry else b
        else:
            cur = (cur + "\n\n" + b).strip() if cur else b
    if cur:
        chunks.append(cur)
    # fold a tiny trailing chunk back into its predecessor
    if len(chunks) >= 2 and len(chunks[-1]) < config.CHUNK_MIN_CHARS and "|" not in chunks[-1]:
        chunks[-2] = (chunks[-2] + "\n\n" + chunks[-1]).strip()
        chunks.pop()
    return chunks


# --------------------------------------------------------------------------------------
# Metadata parsing
# --------------------------------------------------------------------------------------
def parse_cohort(text: str) -> dict | None:
    """Parse a cohort qualifier from a page title (varied phrasings across programs)."""
    if not text:
        return None
    m = re.search(r"(\d{4})\s*/\s*\d{2,4}\s+or\s+(earlier|later)", text, re.I)
    if m:
        return {"raw": m.group(0).strip(), "boundary_year": int(m.group(1)), "direction": m.group(2).lower()}
    m = re.search(r"(?:starting|start|entering|enter)\b[^.]{0,40}?September\s+(\d{4})", text, re.I)
    if m:
        return {"raw": m.group(0).strip(), "boundary_year": int(m.group(1)), "direction": "later"}
    m = re.search(r"(?:prior to|before)\s+September\s+(\d{4})", text, re.I)
    if m:
        return {"raw": m.group(0).strip(), "boundary_year": int(m.group(1)), "direction": "earlier"}
    m = re.search(r"(\d{4})[^.]{0,12}?\bor\s+(earlier|later)", text, re.I)
    if m:
        return {"raw": m.group(0).strip(), "boundary_year": int(m.group(1)), "direction": m.group(2).lower()}
    return None


def parse_cohort_slug(path_key: str) -> dict | None:
    m = re.search(r"(20\d\d)\d{0,2}-or-(earlier|later)", path_key)
    if m:
        return {"raw": m.group(0), "boundary_year": int(m.group(1)), "direction": m.group(2)}
    m = re.search(r"starting-september-(\d{4})", path_key)
    if m:
        return {"raw": m.group(0), "boundary_year": int(m.group(1)), "direction": "later"}
    m = re.search(r"prior-september-(\d{4})", path_key)
    if m:
        return {"raw": m.group(0), "boundary_year": int(m.group(1)), "direction": "earlier"}
    return None


def parse_subject(path_key: str) -> str | None:
    m = re.search(r"course-descriptions/subject/([a-z]+)v$", path_key)
    return m.group(1).upper() if m else None


def parse_node_id(soup) -> int | None:
    sl = soup.find("link", rel="shortlink")
    if sl and sl.get("href"):
        m = re.search(r"/node/(\d+)", sl["href"])
        if m:
            return int(m.group(1))
    el = soup.find(attrs={"data-history-node-id": True})
    if el:
        try:
            return int(el["data-history-node-id"])
        except (ValueError, KeyError):
            pass
    return None


def parse_breadcrumb(soup, page_title: str) -> list[str]:
    nav = soup.select_one("nav.nav-breadcrumbs") or soup.select_one("#block-breadcrumbs")
    crumbs: list[str] = []
    if nav:
        for a in nav.find_all("a"):
            t = a.get_text(strip=True)
            if t and t.lower() != "breadcrumb":
                crumbs.append(t)
    if page_title and (not crumbs or crumbs[-1] != page_title):
        crumbs.append(page_title)
    return crumbs


def classify(breadcrumb: list[str], page_title: str) -> tuple[str | None, str | None, str | None]:
    faculty = program = None
    for c in breadcrumb:
        if faculty is None and re.search(r"\b(Faculty|School|College)\b", c):
            faculty = c
        if program is None and re.match(
            r"(Bachelor|Master|Doctor|Doctoral|Diploma|Certificate|Associate|B\.[A-Za-z]|M\.[A-Za-z])", c):
            program = c
    specialization = None
    if program and page_title and page_title != program and not re.search(
        r"requirement|introduction|admission|regulation|advising|policy|registration|examination", page_title, re.I):
        specialization = page_title
    return faculty, program, specialization


def page_type(path_key: str, page_title: str, cohort, subject_code,
              program=None, has_tables=False) -> str:
    if subject_code:
        return "course-listing"
    if path_key.startswith("campus-wide-policies-and-regulations"):
        return "policy"
    if cohort:
        return "cohort-requirements"
    if re.search(r"requirement", page_title or "", re.I):
        return "requirements"
    # A page under a degree program that carries requirement tables (e.g. the CS
    # specialization page, titled just "Computer Science") is really a requirements page.
    if program and has_tables:
        return "requirements"
    return "landing"


def compose_title(program, page_title, cohort, edition_year) -> str:
    bits = []
    if program and program not in (page_title or ""):
        bits.append(program)
    bits.append(page_title or "")
    label = " — ".join(b for b in bits if b)
    if cohort and cohort["raw"].lower() not in label.lower():
        label += f" ({cohort['raw']})"
    return f"{label} [{edition_year}]"


def compose_text(title: str, section: str, heading: str | None, body: str) -> str:
    head = f"{title} — {section}" if section else title
    if heading and heading.lower() not in title.lower():
        head += f"\n\n## {heading}"
    return f"{head}\n\n{body}".strip()


# --------------------------------------------------------------------------------------
# Public: page record -> chunk records
# --------------------------------------------------------------------------------------
def page_record_to_chunks(record: dict) -> list[dict]:
    soup = BeautifulSoup(record["raw_html"], "lxml")
    main = (soup.select_one("#primary-content")
            or soup.select_one("#block-kraken-mainpagecontent")
            or soup.select_one("main")
            or soup)

    # Read title + breadcrumb BEFORE stripping (stripping <nav>/<h1> mutates the shared tree).
    h1 = main.select_one("h1") or soup.select_one("main h1") or soup.select_one("h1")
    page_title = h1.get_text(strip=True) if h1 else record["path_key"].split("/")[-1].replace("-", " ").title()
    breadcrumb = parse_breadcrumb(soup, page_title)

    for sel in STRIP_SELECTORS:
        for tag in main.select(sel):
            tag.decompose()
    # #primary-content is the whole main column (excludes the sidebar, which is a sibling). Use
    # it directly rather than .node__content, which on taxonomy/course pages holds only the intro.
    content_root = main

    section_label = " > ".join(breadcrumb[1:]) if len(breadcrumb) > 1 else " > ".join(breadcrumb)
    subject_code = parse_subject(record["path_key"])
    cohort = parse_cohort(page_title) or parse_cohort_slug(record["path_key"])
    faculty, program, specialization = classify(breadcrumb, page_title)
    has_tables = content_root.find("table") is not None
    ptype = page_type(record["path_key"], page_title, cohort, subject_code, program, has_tables)
    title = compose_title(program, page_title, cohort, record["edition_year"])
    node_id = parse_node_id(soup)

    canonical = record.get("canonical_url") or ""
    url = canonical if canonical.startswith("http") else record["url"]
    base = {
        "title": title,
        "section": section_label,
        "url": url,
        "edition_year": record["edition_year"],
        "source": record["source"],
        "path_key": record["path_key"],
        "faculty": faculty,
        "program": program,
        "specialization": specialization,
        "cohort_qualifier": cohort,
        "page_type": ptype,
        "subject_code": subject_code,
        "node_id": node_id,
        "fetched_at": record.get("fetched_at"),
        "content_hash": record.get("content_hash"),
        "last_modified": record.get("last_modified"),
    }

    chunks: list[dict] = []
    for section in split_sections(flow_elements(content_root)):
        body = render_section(section)
        if not body.strip():
            continue
        for piece in chunk_body(body):
            rec = dict(base)
            rec["heading"] = section["heading"]
            rec["text"] = compose_text(title, section_label, section["heading"], piece)
            chunks.append(rec)
    return chunks


def iter_page_records():
    """Yield the current page record for each url in the manifest (skips stale snapshots)."""
    if not config.MANIFEST_PATH.exists():
        return
    manifest = json.loads(config.MANIFEST_PATH.read_text(encoding="utf-8"))
    for meta in manifest.values():
        jp = config.PROJECT_ROOT / meta["json_path"]
        if jp.exists():
            yield json.loads(jp.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------------------
# CLI (quick inspection)
# --------------------------------------------------------------------------------------
def _print_one(path: str) -> None:
    record = json.loads((config.PROJECT_ROOT / path).read_text(encoding="utf-8")) \
        if not path.startswith("{") else json.loads(path)
    chunks = page_record_to_chunks(record)
    print(f"{record['url']}\n  {len(chunks)} chunks\n")
    for i, c in enumerate(chunks):
        print(f"--- chunk {i} (page_type={c['page_type']}, cohort={c['cohort_qualifier']}) ---")
        print(c["text"][:800])
        print()


def _print_stats() -> None:
    pages = chunks_total = 0
    by_type: dict[str, int] = {}
    for record in iter_page_records():
        pages += 1
        for c in page_record_to_chunks(record):
            chunks_total += 1
            by_type[c["page_type"]] = by_type.get(c["page_type"], 0) + 1
    print(f"Pages: {pages}   Chunks: {chunks_total}")
    for t, n in sorted(by_type.items(), key=lambda kv: -kv[1]):
        print(f"  {n:5d}  {t}")


def main() -> None:
    if len(sys.argv) > 1:
        _print_one(sys.argv[1])
    else:
        _print_stats()


if __name__ == "__main__":
    main()

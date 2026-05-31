"""Parse CGST Act PDF — v3: robust section boundary detection, no truncation."""
import json, re, logging
from pathlib import Path

import pdfplumber

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ACT_PATH = Path("ml/data/raw_acts/cgst_act.pdf")
OUT_DIR = Path("ml/data/parsed_acts")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHAPTER_RANGES = [
    (1, 1, "Preliminary"),
    (2, 2, "Definitions"),
    (3, 6, "Levy and Collection of Tax"),
    (7, 11, "Time and Value of Supply"),
    (12, 14, "Input Tax Credit"),
    (15, 15, "Registration"),
    (16, 22, "Returns"),
    (23, 31, "Payment of Tax"),
    (32, 38, "Assessment and Audit"),
    (39, 48, "Appeals"),
    (49, 57, "Offences and Penalties"),
    (58, 68, "Miscellaneous"),
]


def infer_chapter(n):
    for start, end, name in CHAPTER_RANGES:
        if start <= n <= end:
            return name
    return "Other"


def extract_title(body: str) -> str:
    first = body.split("\n")[0].strip() if body else ""
    m = re.match(r"^\(1\)\s+([A-Z][^(\n]+)", first)
    if m:
        return m.group(1).strip().rstrip(",")
    m = re.match(r"^([A-Z][^(\n]+?)\s*\n", body)
    if m:
        return m.group(1).strip().rstrip(",")
    m = re.match(r"^([A-Z][^(\n]+)", first)
    if m:
        return m.group(1).strip().rstrip(",")
    return ""


def parse_act():
    if not ACT_PATH.exists():
        log.error(f"CGST Act PDF not found at {ACT_PATH}")
        return 0

    log.info(f"Parsing {ACT_PATH}...")
    full_text = ""
    with pdfplumber.open(ACT_PATH) as pdf:
        for i, page in enumerate(pdf.pages):
            txt = page.extract_text() or ""
            full_text += txt + "\n"
            if i % 20 == 0:
                log.info(f"  Page {i}/{len(pdf.pages)}...")

    log.info(f"Total extracted chars: {len(full_text)}")

    # Strategy: find section numbers that appear after 2+ newlines or at start-of-text
    # This avoids matching numbers inside running text
    boundary_matches = list(re.finditer(
        r"(?:^|\n{2,})\s*(\d{1,3})\.\s*\n*",
        full_text
    ))
    log.info(f"Boundary pattern found {len(boundary_matches)} matches")

    cands = []
    for m in boundary_matches:
        n = int(m.group(1))
        if 1 <= n <= 174:
            cands.append((n, m.start(), m.end()))

    # Deduplicate: keep first occurrence of each section number
    seen = set()
    unique = []
    for n, start, end in cands:
        if n not in seen:
            seen.add(n)
            unique.append((n, start, end))

    log.info(f"Unique sections: {len(unique)}")

    if len(unique) < 30:
        log.warning(f"Only {len(unique)} unique sections — trying broader pattern...")
        # Broader: match \d+\. at line start
        broad = list(re.finditer(r"(?:^|\n)\s*(\d{1,3})\.\s*(?:\(1\)|[A-Z])", full_text))
        seen2 = set()
        unique = []
        for m in broad:
            n = int(m.group(1))
            if 1 <= n <= 174 and n not in seen2:
                seen2.add(n)
                unique.append((n, m.start(), m.end()))
        log.info(f"Broad pattern found {len(unique)} unique sections")

    sections = []
    for i, (snum, _start, end) in enumerate(unique):
        nxt_start = unique[i + 1][1] if i + 1 < len(unique) else len(full_text)
        body = full_text[end:nxt_start].strip()

        title = extract_title(body)
        if not title:
            title = f"Section {snum}"

        sections.append({
            "section_number": snum,
            "section_title": title,
            "chapter": infer_chapter(snum),
            "full_text": body,
            "char_count": len(body),
        })

    log.info(f"Total sections: {len(sections)}")

    for s in sections:
        out_path = OUT_DIR / f"cgst_section_{s['section_number']}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2, ensure_ascii=False)

    char_counts = [s["char_count"] for s in sections]
    log.info(f"Char counts — min: {min(char_counts)}, max: {max(char_counts)}, avg: {sum(char_counts)//len(char_counts)}")
    return len(sections)


if __name__ == "__main__":
    parse_act()

"""Parse CGST Act PDF — v2: handle multi-column government PDF layout."""
import json, re, logging
from pathlib import Path

import pdfplumber

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ACT_PATH = Path("ml/data/raw_acts/cgst_act.pdf")
OUT_DIR = Path("ml/data/parsed_acts")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Section header patterns for this specific PDF
# The CGST Act sections are numbered 1 to 174
# Headers look like: "Short title,\nextent and\ncommencement.\n\n1. (1) This Act..."
# Or: "Definitions. 2. In this Act, unless..."
SECTION_PATTERN = re.compile(
    r"(?:^|\n{2,})\s*(\d+)\.\s*\n*\s*\(1\)\s+([A-Z][^.]*(?:\.\s*)?)",
    re.MULTILINE
)
# Also catch sections where title comes before number
ALT_SECTION_PATTERN = re.compile(
    r"([A-Z][a-zA-Z\s,]+)\.\s*\n*\s*(\d+)\.\s*\n*\s*\(",
    re.MULTILINE
)


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

    # Try primary pattern: "N.\n\n(1) ..."
    matches = list(SECTION_PATTERN.finditer(full_text))
    log.info(f"Primary pattern found {len(matches)} matches")

    sections = []
    if len(matches) >= 30:
        log.info("Using primary pattern results...")
        for m in matches:
            snum = int(m.group(1))
            title = m.group(2).strip()
            sections.append({
                "section_number": snum,
                "section_title": title,
                "full_text": "",
                "char_count": 0,
            })
    else:
        log.info("Primary pattern insufficient — trying simple number pattern...")
        matches = list(re.finditer(r"(?:^|\n)\s*(\d{1,3})\.\s*\n", full_text))
        log.info(f"Simple section number pattern found {len(matches)}")

        for i, m in enumerate(matches):
            snum = int(m.group(1))
            if snum < 1 or snum > 174:
                continue
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
            body = full_text[start:end].strip()
            first_line = body.split("\n")[0].strip() if body else ""
            title_match = re.match(r"^(?:\(1\)\s+)?([A-Z][^.]+)", first_line)
            title = title_match.group(1).strip() if title_match else f"Section {snum}"

            existing = next((s for s in sections if s["section_number"] == snum), None)
            if existing:
                if len(body) > len(existing["full_text"]):
                    existing["full_text"] = body[:2000]
                    existing["char_count"] = len(body)
            else:
                sections.append({
                    "section_number": snum,
                    "section_title": title,
                    "full_text": body[:2000],
                    "char_count": len(body),
                })

    sections = sorted(sections, key=lambda x: x["section_number"])

    CHAPTER_RANGES = [
        (1, 1, "Preliminary"),
        (2, 2, "Definitions"),
        (7, 11, "Levy and Collection of Tax"),
        (12, 14, "Time and Value of Supply"),
        (15, 15, "Input Tax Credit"),
        (16, 22, "Registration"),
        (23, 31, "Returns"),
        (32, 38, "Payment of Tax"),
        (39, 48, "Assessment and Audit"),
        (49, 57, "Appeals"),
        (58, 68, "Offences and Penalties"),
        (69, 79, "Miscellaneous"),
    ]

    def infer_chapter(n):
        for start, end, name in CHAPTER_RANGES:
            if start <= n <= end:
                return name
        return "Other"

    for s in sections:
        s["chapter"] = infer_chapter(s["section_number"])

    for s in sections:
        out_path = OUT_DIR / f"cgst_section_{s['section_number']}.json"
        with open(out_path, "w") as f:
            json.dump(s, f, indent=2)

    log.info(f"Parsed {len(sections)} sections")
    if len(sections) < 80:
        log.warning(f"Only {len(sections)} sections — expected 80+. The PDF text extraction may have limitations.")
    return len(sections)


if __name__ == "__main__":
    parse_act()

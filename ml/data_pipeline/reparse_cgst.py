"""Re-parse CGST Act — extract full section text by finding section number positions in the raw PDF text."""
import json, re, logging
from pathlib import Path

import pdfplumber

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ACT_PATH = Path("ml/data/raw_acts/cgst_act.pdf")
OUT_DIR = Path("ml/data/parsed_acts")
OUT_DIR.mkdir(parents=True, exist_ok=True)

log.info("Extracting full text from CGST Act PDF...")
full_text = ""
with pdfplumber.open(ACT_PATH) as pdf:
    for i, page in enumerate(pdf.pages):
        txt = page.extract_text() or ""
        full_text += txt + "\n"

log.info(f"Total chars: {len(full_text)}")

# Find all section number occurrences like "N." where N is 1-174
# Use a pattern that catches section headers reliably
all_positions = []
for m in re.finditer(r"(?:^|\n)\s*(\d{1,3})\.\s*(?:\(1\)|[A-Z(])", full_text):
    snum = int(m.group(1))
    if 1 <= snum <= 174:
        all_positions.append((snum, m.start()))

log.info(f"Found {len(all_positions)} section positions")

# Remove duplicates — keep first occurrence of each section number
seen = {}
for snum, pos in all_positions:
    if snum not in seen or pos < seen[snum]:
        seen[snum] = pos

sorted_sections = sorted(seen.items())  # [(1, pos), (2, pos), ...]

# Find chapter boundaries from the text
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

# Extract full text for each section
sections = []
for i, (snum, start_pos) in enumerate(sorted_sections):
    # End is the start of the next section, or end of text
    if i + 1 < len(sorted_sections):
        end_pos = sorted_sections[i + 1][1]
    else:
        end_pos = len(full_text)

    body = full_text[start_pos:end_pos].strip()

    # Extract title: first line or first sentence
    first_line = body.split("\n")[0].strip()
    title = first_line[:120] if first_line else f"Section {snum}"

    sections.append({
        "section_number": snum,
        "section_title": title,
        "chapter": infer_chapter(snum),
        "full_text": body,
        "char_count": len(body),
    })

log.info(f"Extracted {len(sections)} sections with full body text")

# Write all sections
for s in sections:
    out_path = OUT_DIR / f"cgst_section_{s['section_number']}.json"
    with open(out_path, "w") as f:
        json.dump(s, f, indent=2)

# Show samples
for s in sections[:5]:
    log.info(f"  Section {s['section_number']}: {s['section_title'][:60]}... ({s['char_count']} chars)")

key_sections = [s for s in sections if s["section_number"] in (16, 17, 18)]
log.info(f"\nKey ITC sections: {[s['section_number'] for s in key_sections]}")
for s in key_sections:
    log.info(f"  Section {s['section_number']}: {s['char_count']} chars")
    log.info(f"    Preview: {s['full_text'][:200]}...")

log.info(f"\nDone — {len(sections)} sections saved to {OUT_DIR}")

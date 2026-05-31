"""Legal-hierarchy-aware chunker for CGST Act and CBIC circulars.
Preserves Section -> Sub-section -> Clause -> Proviso hierarchy.
Handles contaminated PDF extraction gracefully."""
import json, re, logging
from pathlib import Path

import tiktoken

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

SECTIONS_DIR = Path("ml/data/parsed_acts")
CIRCULARS_DIR = Path("ml/data/metadata")
OUTPUT_PATH = Path("ml/data/processed/all_chunks.jsonl")

MAX_TOKENS = 800
ENCODER = tiktoken.get_encoding("cl100k_base")

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


def infer_chapter(n: int) -> str:
    for start, end, name in CHAPTER_RANGES:
        if start <= n <= end:
            return name
    return "Other"


def count_tokens(text: str) -> int:
    return len(ENCODER.encode(text))


class LegalChunker:

    def __init__(self, sections_dir: str | Path, circulars_dir: str | Path):
        self.sections_dir = Path(sections_dir)
        self.circulars_dir = Path(circulars_dir)

    def chunk_all(self, output_path: str | Path) -> list[dict]:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        chunks = []
        chunks.extend(self._chunk_cgst_act())
        chunks.extend(self._chunk_circulars())

        # Final dedup by chunk_id (keep last occurrence)
        seen = {}
        for c in chunks:
            cid = c["chunk_id"]
            if cid in seen:
                # Deduplicate by adding suffix
                n = 2
                while f"{cid}_{n}" in seen:
                    n += 1
                c["chunk_id"] = f"{cid}_{n}"
            seen[c["chunk_id"]] = c
        chunks = list(seen.values())

        with open(output_path, "w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

        log.info(f"Total chunks: {len(chunks)}")
        if chunks:
            tokens = [c["token_count"] for c in chunks]
            log.info(f"  Avg tokens: {sum(tokens) / len(tokens):.0f}")
            log.info(f"  Min tokens: {min(tokens)}, Max tokens: {max(tokens)}")
        return chunks

    def _chunk_cgst_act(self) -> list[dict]:
        chunks = []
        for path in sorted(self.sections_dir.glob("cgst_section_*.json")):
            with open(path, encoding="utf-8") as f:
                section = json.load(f)

            snum = section["section_number"]
            title = section.get("section_title", "")
            body = section.get("full_text", "")
            chapter = section.get("chapter", infer_chapter(snum))

            if not body or len(body) < 50:
                continue

            # Detect contamination: if section has > 30 unique (N) patterns, it's merged with another section
            sub_nums = set(re.findall(r"\n\s*\((\d+)\)\s+", body))
            contaminated = len(sub_nums) > 30

            if contaminated:
                log.info(f"Section {snum}: contaminated ({len(sub_nums)} sub-section markers), treating as single chunk")
                chunk = self._make_fallback_chunk(snum, title, chapter, body)
                if chunk:
                    chunks.append(chunk)
                continue

            sub_sections = self._parse_sub_sections(body)

            if not sub_sections:
                chunk = self._make_section_chunk(snum, title, chapter, body, "0")
                if isinstance(chunk, list):
                    chunks.extend(chunk)
                elif chunk:
                    chunks.append(chunk)
                continue

            for ss_num, ss_text in sub_sections:
                chunk = self._make_section_chunk(snum, title, chapter, ss_text, ss_num)
                if isinstance(chunk, list):
                    chunks.extend(chunk)
                elif chunk:
                    chunks.append(chunk)

        log.info(f"CGST chunks: {len(chunks)}")
        sections_used = len({c.get("section") for c in chunks})
        log.info(f"  Sections used: {sections_used}")
        return chunks

    def _make_fallback_chunk(self, snum: int, title: str, chapter: str,
                              body: str) -> dict | None:
        """Create a single chunk for a contaminated/merged section."""
        header = f"Section {snum}: {title}"
        full_text = f"{header}\n\n{body}"
        token_count = count_tokens(full_text)

        return self._truncate_to_max({
            "chunk_id": f"cgst_s{snum}",
            "citation": f"CGST Act, 2017 — Section {snum}",
            "source_type": "cgst_act",
            "section": snum,
            "sub_section": "0",
            "chapter": chapter,
            "parent_context": header,
            "text": full_text,
            "token_count": token_count,
        })

    def _parse_sub_sections(self, body: str) -> list[tuple[str, str]]:
        """Parse body into (sub_section_number, text) pairs.
        Only splits on subsection markers that start a new line."""
        sub_pattern = re.compile(r"\n\s*\((\d+)\)\s+")
        parts = list(sub_pattern.split(body))

        if len(parts) < 2:
            return []

        header = parts[0].strip()
        result = []

        i = 1
        while i < len(parts):
            ss_num = parts[i]
            remaining_parts = parts[i + 1:]
            next_idx = None
            for j in range(1, len(remaining_parts), 2):
                if re.match(r"^\d+$", remaining_parts[j]):
                    next_idx = j
                    break

            if next_idx is not None:
                ss_text = " ".join(remaining_parts[:next_idx])
                i += next_idx + 1
            else:
                ss_text = " ".join(remaining_parts)
                i = len(parts)

            full_text = f"{header.strip()}\n\n({ss_num}) {ss_text.strip()}"
            result.append((ss_num, full_text.strip()))

        return result

    def _truncate_to_max(self, chunk: dict) -> dict:
        if chunk["token_count"] > MAX_TOKENS:
            tokens = ENCODER.encode(chunk["text"])
            truncated = ENCODER.decode(tokens[:MAX_TOKENS - 20])
            chunk["text"] = truncated + "\n\n[...truncated]"
            chunk["token_count"] = count_tokens(chunk["text"])
        return chunk

    def _make_section_chunk(self, snum: int, title: str, chapter: str,
                            text: str, ss_num: str) -> dict | list[dict] | None:
        header = f"Section {snum}: {title}"
        full_text = f"{header}\n\n{text}"
        token_count = count_tokens(full_text)

        if token_count <= MAX_TOKENS:
            return self._truncate_to_max({
                "chunk_id": f"cgst_s{snum}_ss{ss_num}",
                "citation": f"CGST Act, 2017 — Section {snum}({ss_num})",
                "source_type": "cgst_act",
                "section": snum,
                "sub_section": ss_num,
                "chapter": chapter,
                "parent_context": header,
                "text": full_text,
                "token_count": token_count,
            })

        clauses = self._split_into_clauses(text)
        if len(clauses) > 1:
            result = []
            current_text = header
            for clause in clauses:
                candidate = f"{current_text}\n\n{clause}"
                if count_tokens(candidate) > MAX_TOKENS and current_text != header:
                    cidx = len(result)
                    result.append(self._truncate_to_max({
                        "chunk_id": f"cgst_s{snum}_ss{ss_num}_c{cidx}",
                        "citation": f"CGST Act, 2017 — Section {snum}({ss_num})",
                        "source_type": "cgst_act",
                        "section": snum,
                        "sub_section": ss_num,
                        "chapter": chapter,
                        "parent_context": header,
                        "text": current_text,
                        "token_count": count_tokens(current_text),
                    }))
                    current_text = f"{header}\n\n{clause}"
                else:
                    current_text = candidate

            if current_text:
                cidx = len(result)
                result.append(self._truncate_to_max({
                    "chunk_id": f"cgst_s{snum}_ss{ss_num}_c{cidx}",
                    "citation": f"CGST Act, 2017 — Section {snum}({ss_num})",
                    "source_type": "cgst_act",
                    "section": snum,
                    "sub_section": ss_num,
                    "chapter": chapter,
                    "parent_context": header,
                    "text": current_text,
                    "token_count": count_tokens(current_text),
                }))
            return result

        return self._truncate_to_max({
            "chunk_id": f"cgst_s{snum}_ss{ss_num}",
            "citation": f"CGST Act, 2017 — Section {snum}({ss_num})",
            "source_type": "cgst_act",
            "section": snum,
            "sub_section": ss_num,
            "chapter": chapter,
            "parent_context": header,
            "text": full_text,
            "token_count": token_count,
        })

    def _split_into_clauses(self, text: str) -> list[str]:
        clause_pattern = re.compile(r"\n\s*\(([a-z])\)\s+")
        parts = clause_pattern.split(text)
        if len(parts) < 2:
            return [text]

        clauses = []
        current = parts[0].strip()
        for i in range(1, len(parts), 2):
            clause_text = parts[i + 1] if i + 1 < len(parts) else ""
            if current:
                clauses.append(current)
            current = f"({parts[i]}) {clause_text.strip()}"
        if current:
            clauses.append(current)
        return clauses

    def _chunk_circulars(self) -> list[dict]:
        chunks = []
        for path in sorted(self.circulars_dir.glob("circular_*.json")):
            with open(path, encoding="utf-8") as f:
                meta = json.load(f)

            circular_n = meta.get("circular_number", "")
            date = meta.get("date", "")
            sections_ref = meta.get("sections_referenced", [])
            text = meta.get("raw_text", "")

            if not text or len(text) < 50:
                continue

            chunk_id = f"cbic_circular_{circular_n}"
            citation = f"CBIC Circular No. {circular_n}"
            if date:
                citation += f" dated {date}"

            token_count = count_tokens(text)
            chunks.append({
                "chunk_id": chunk_id,
                "citation": citation,
                "source_type": "cbic_circular",
                "circular_number": circular_n,
                "sections_referenced": sections_ref,
                "date": date,
                "text": text,
                "token_count": token_count,
            })

        log.info(f"Circular chunks: {len(chunks)}")
        return chunks


if __name__ == "__main__":
    chunker = LegalChunker(SECTIONS_DIR, CIRCULARS_DIR)
    chunks = chunker.chunk_all(OUTPUT_PATH)
    print(f"\nDone — {len(chunks)} chunks written to {OUTPUT_PATH}")

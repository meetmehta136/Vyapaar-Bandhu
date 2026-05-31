"""Validate chunk output with 8 checks."""
import json, sys
from pathlib import Path

CHUNKS_PATH = Path("ml/data/processed/all_chunks.jsonl")

checks_passed = 0
checks_total = 0


def check(name: str, condition: bool, detail: str = ""):
    global checks_passed, checks_total
    checks_total += 1
    status = "PASS" if condition else "FAIL"
    if condition:
        checks_passed += 1
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


def run():
    if not CHUNKS_PATH.exists():
        print("[FAIL] all_chunks.jsonl not found")
        sys.exit(1)

    chunks = []
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))

    print(f"\nLoaded {len(chunks)} chunks from {CHUNKS_PATH}\n")

    # CHECK 1: No chunk exceeds 800 tokens
    over = [c for c in chunks if c.get("token_count", 0) > 800]
    check("No chunk exceeds 800 tokens", len(over) == 0,
          f"{len(over)} chunks over limit")

    # CHECK 2: Every chunk has required fields
    required = ["chunk_id", "citation", "source_type", "text", "token_count"]
    missing = [c for c in chunks if not all(k in c for k in required)]
    check("Every chunk has chunk_id, citation, source_type, text, token_count",
          len(missing) == 0, f"{len(missing)} chunks missing fields")

    # CHECK 3: No chunk has empty text (len < 50 chars)
    empty = [c for c in chunks if len(c.get("text", "")) < 50]
    check("No chunk has empty text", len(empty) == 0,
          f"{len(empty)} chunks with < 50 chars")

    # CHECK 4: CGST chunks have section, parent_context fields
    cgst_chunks = [c for c in chunks if c.get("source_type") == "cgst_act"]
    cgst_ok = all(
        "section" in c and "parent_context" in c
        for c in cgst_chunks
    )
    check("CGST chunks have section + parent_context fields",
          cgst_ok, f"{len(cgst_chunks)} cgst chunks checked")

    # CHECK 5: Circular chunks have circular_number
    circ_chunks = [c for c in chunks if c.get("source_type") == "cbic_circular"]
    circ_ok = all("circular_number" in c for c in circ_chunks)
    check("Circular chunks have circular_number fields",
          circ_ok, f"{len(circ_chunks)} circular chunks checked")

    # CHECK 6: chunk_ids are unique
    ids = [c["chunk_id"] for c in chunks]
    check("chunk_ids are unique", len(ids) == len(set(ids)),
          f"{len(ids) - len(set(ids))} duplicates")

    # CHECK 7: Section 17 has at least 5 sub-chunks
    s17_chunks = [c for c in cgst_chunks if c.get("section") == 17]
    check("Section 17 has at least 5 chunks",
          len(s17_chunks) >= 5, f"Found {len(s17_chunks)} chunks for section 17")

    # CHECK 8: At least 100 total chunks
    check("At least 100 total chunks", len(chunks) >= 100,
          f"{len(chunks)} total")

    # Summary
    print(f"\n{'='*50}")
    print(f"Validation: {checks_passed}/{checks_total} passed")
    if checks_passed == checks_total:
        print(
            f"\nValidation PASSED — {len(chunks)} chunks ready for indexing")
    else:
        print(
            f"\nValidation FAILED — fix issues above before proceeding")
        sys.exit(1)

    # Bonus stats
    tokens = [c.get("token_count", 0) for c in chunks]
    print(f"\nStats:")
    print(f"  Total chunks: {len(chunks)}")
    print(f"  CGST chunks: {len(cgst_chunks)}")
    print(f"  Circular chunks: {len(circ_chunks)}")
    print(f"  Avg tokens: {sum(tokens) / len(tokens):.0f}")
    print(f"  Unique sections: {len(set(c.get('section') for c in cgst_chunks if c.get('section')))}")


if __name__ == "__main__":
    run()

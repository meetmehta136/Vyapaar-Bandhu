"""Build citation graph from circular metadata + parsed act sections."""
import json, logging
from pathlib import Path
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

META_DIR = Path("ml/data/metadata")
PARSED_DIR = Path("ml/data/parsed_acts")
OUT_PATH = Path("ml/data/citation_graph.json")


def build_graph():
    section_to_circulars: dict[str, list[int]] = defaultdict(list)
    circular_to_sections: dict[str, list[str]] = {}
    total_processed = 0

    for meta_path in sorted(META_DIR.glob("circular_*.json")):
        with open(meta_path) as f:
            meta = json.load(f)

        circ_num = str(meta.get("circular_number", ""))
        sections = meta.get("sections_referenced", [])

        total_processed += 1
        circular_to_sections[circ_num] = [str(s) for s in sections]

        for s in sections:
            section_to_circulars[str(s)].append(meta["circular_number"])

    # Also collect all parsed section numbers from the act
    parsed_sections = set()
    for p in PARSED_DIR.glob("cgst_section_*.json"):
        parsed_sections.add(p.stem.replace("cgst_section_", ""))

    graph = {
        "section_to_circulars": {k: v for k, v in section_to_circulars.items()},
        "circular_to_sections": circular_to_sections,
        "total_circulars_processed": total_processed,
        "total_sections_in_act": len(parsed_sections),
        "total_sections_referenced": len(section_to_circulars),
    }

    with open(OUT_PATH, "w") as f:
        json.dump(graph, f, indent=2)

    log.info(f"Citation graph saved to {OUT_PATH}")
    log.info(f"  Circulars processed: {total_processed}")
    log.info(f"  Act sections parsed: {len(parsed_sections)}")
    log.info(f"  Unique sections referenced by circulars: {len(section_to_circulars)}")
    return graph


if __name__ == "__main__":
    build_graph()

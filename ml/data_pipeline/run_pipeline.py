"""Run the full data pipeline: seed → parse → build citation graph.
CBIC scraper runs first (best-effort), then seed + parse + graph build."""
import subprocess, sys, logging, json
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

PIPELINE_DIR = Path("ml/data_pipeline")

steps = [
    ("scraper.py", "CBIC Circular Scraper", True),
    ("seed_circulars.py", "Seed Circular Metadata", False),
    ("parse_cgst_act.py", "CGST Act Parser", True),
    ("build_citation_graph.py", "Citation Graph Builder", True),
]


def run():
    for script, name, required in steps:
        log.info(f"=== {name} ===")
        result = subprocess.run(
            [sys.executable, str(PIPELINE_DIR / script)],
            capture_output=True, text=True, cwd="."
        )
        out = result.stdout
        err = result.stderr
        print(out)
        if err:
            print(err[:500])

        if result.returncode != 0:
            if required:
                log.error(f"{name} FAILED — aborting")
                return False
            log.warning(f"{name} had errors but continuing")

    # Count everything
    meta_count = len(list(Path("ml/data/metadata").glob("circular_*.json")))
    parsed_count = len(list(Path("ml/data/parsed_acts").glob("cgst_section_*.json")))
    raw_count = len(list(Path("ml/data/raw_circulars").glob("circular_*.pdf")))
    total_files = sum(1 for _ in Path("ml/data").rglob("*"))

    cg_path = Path("ml/data/citation_graph.json")
    if cg_path.exists():
        with open(cg_path) as f:
            cg = json.load(f)
        cg_entries = len(cg.get("section_to_circulars", {}))
        total_circ = cg.get("total_circulars_processed", 0)
    else:
        cg_entries = 0
        total_circ = 0

    log.info("=" * 55)
    log.info("DATA PIPELINE SUMMARY")
    log.info(f"  Circulars downloaded:         {raw_count}")
    log.info(f"  Circular metadata files:      {meta_count}")
    log.info(f"  CGST Act sections parsed:     {parsed_count}")
    log.info(f"  Citation graph entries:       {cg_entries}")
    log.info(f"  Total files in ml/data/:      {total_files}")
    log.info("=" * 55)
    return True


if __name__ == "__main__":
    run()

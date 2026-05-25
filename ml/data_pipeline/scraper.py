"""CBIC GST Circular scraper — quick probe + early exit if site unreachable."""
import json, os, time, re, logging
from pathlib import Path

import requests
import pdfplumber

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

RAW_DIR = Path("ml/data/raw_circulars")
META_DIR = Path("ml/data/metadata")
FAILED_LOG = Path("ml/data/failed_downloads.txt")
RAW_DIR.mkdir(parents=True, exist_ok=True)
META_DIR.mkdir(parents=True, exist_ok=True)

SECTION_RE = re.compile(r"[Ss]ection\s+(\d+)(?:\((\d+)\))?(?:\(([a-zA-Z])\))?")
DATE_RE = re.compile(r"dated\s+(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})", re.IGNORECASE)


def probe_site() -> bool:
    """Quick probe: try downloading one circular. Returns True if site is reachable."""
    for url in [
        "https://cbic-gst.gov.in/pdf/Circular-No-1-2017.pdf",
        "https://cbic-gst.gov.in/pdf/cgst-circular-1.pdf",
        "https://cbic-gst.gov.in/GST-Circulars/AD-1.pdf",
    ]:
        try:
            r = requests.get(url, timeout=5, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and len(r.content) > 1000:
                path = RAW_DIR / "circular_1.pdf"
                with open(path, "wb") as f:
                    f.write(r.content)
                log.info(f"Site reachable! Downloaded circular_1.pdf from {url}")
                return True
        except requests.RequestException:
            continue
    log.warning("CBIC site unreachable — will use seeded circular metadata instead")
    return False


def try_download(n: int) -> tuple[str | None, str | None]:
    years = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]
    for y in years:
        for tpl in [
            f"https://cbic-gst.gov.in/pdf/Circular-No-{n}-{y}.pdf",
            f"https://cbic-gst.gov.in/pdf/cgst-circular-{n}.pdf",
            f"https://cbic-gst.gov.in/GST-Circulars/AD-{n}.pdf",
        ]:
            try:
                r = requests.get(tpl, timeout=5, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200 and len(r.content) > 1000:
                    path = str(RAW_DIR / f"circular_{n}.pdf")
                    with open(path, "wb") as f:
                        f.write(r.content)
                    return tpl, path
            except requests.RequestException:
                continue
    return None, None


def extract_metadata(n: int, pdf_path: str) -> dict:
    sections, date, preview = set(), None, ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:10]:
                txt = page.extract_text() or ""
                preview += txt
                for m in SECTION_RE.finditer(txt):
                    sections.add(m.group(1))
                if not date:
                    dm = DATE_RE.search(txt)
                    if dm:
                        date = dm.group(1)
    except Exception:
        pass
    return {
        "circular_number": n, "url_used": "", "date": date or "",
        "pdf_path": pdf_path,
        "sections_referenced": sorted(sections, key=lambda x: int(re.sub(r"\D", "", x) or 0)),
        "raw_text": preview[:3000],
    }


def scrape_all(max_n: int = 220):
    if not probe_site():
        log.info("Skipping CBIC scraper — site unreachable. Seed data will be used instead.")
        with open(FAILED_LOG, "w") as f:
            f.write("CBIC site unreachable — no direct downloads\n")
        return 0, []

    downloaded, failed = 0, []
    for n in range(1, max_n + 1):
        url, path = try_download(n)
        if path:
            meta = extract_metadata(n, path)
            meta["url_used"] = url or ""
            with open(META_DIR / f"circular_{n}.json", "w") as f:
                json.dump(meta, f, indent=2)
            downloaded += 1
        else:
            failed.append(n)
        if n % 10 == 0:
            log.info(f"Progress: {n}/{max_n}... ({downloaded} downloaded)")
        time.sleep(0.3)

    with open(FAILED_LOG, "w") as f:
        for n in failed:
            f.write(f"circular_{n}\n")

    log.info(f"\nTotal downloaded: {downloaded}/{max_n}")
    log.info(f"Total failed: {len(failed)}")
    return downloaded, failed


if __name__ == "__main__":
    scrape_all()

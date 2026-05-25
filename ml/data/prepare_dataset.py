"""
Prepare GST classification dataset: clean, augment, split, and upload to HuggingFace.

Pipeline:
  1. Load raw_synthetic.csv
  2. Clean (dedup, filter short/long, junk)
  3. Augment (OCR noise, word shuffle)
  4. Stratified split (test 100/class, train/val 82/18)
  5. Upload to HuggingFace Hub
  6. Print statistics
"""

import csv
import json
import os
import sys
import random
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from sklearn.model_selection import train_test_split
from tqdm import tqdm

from augment import apply_augmentations

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "backend", ".env"))

DATA_DIR = Path(__file__).parent
RAW_FILE = DATA_DIR / "raw_synthetic.csv"
TRAIN_FILE = DATA_DIR / "train.csv"
VAL_FILE = DATA_DIR / "val.csv"
TEST_FILE = DATA_DIR / "test.csv"
STATS_FILE = DATA_DIR / "dataset_stats.json"

# Stratified split: 100 samples per class for held-out test
TEST_SAMPLES_PER_CLASS = 100
VAL_SPLIT = 0.18  # 18% of remaining after test extraction

CLASSES = {
    0: "capital_goods",
    1: "input_services",
    2: "raw_materials",
    3: "motor_vehicles_conveyance",
    4: "food_beverages_catering",
    5: "club_health_beauty",
    6: "personal_employee_benefit",
}
CLASS_TO_ID = {v: k for k, v in CLASSES.items()}

RANDOM_SEED = 42
random.seed(RANDOM_SEED)


def load_raw(path: Path) -> list[dict]:
    if not path.exists():
        print(f"ERROR: {path} not found. Run generate_dataset.py first.")
        sys.exit(1)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def clean(rows: list[dict]) -> list[dict]:
    """Remove duplicates and invalid samples."""
    initial = len(rows)

    # Remove exact duplicates on (text, label, language_variant)
    seen = set()
    deduped = []
    for r in rows:
        key = (r["text"].strip(), r["label"], r["language_variant"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    # Filter by word count
    valid = []
    word_counts = []
    for r in deduped:
        words = r["text"].strip().split()
        wc = len(words)
        word_counts.append(wc)
        if 2 <= wc <= 35:
            valid.append(r)

    # Remove text that is just numbers
    final = []
    for r in valid:
        stripped = r["text"].strip()
        # Check if mostly numbers / special chars
        alpha_count = sum(c.isalpha() for c in stripped)
        if alpha_count > 2:  # at least 3 alphabetic characters
            final.append(r)

    print(f"  Clean: {initial} -> {len(final)} ({initial - len(final)} removed)")
    return final


def augment(rows: list[dict]) -> list[dict]:
    """Apply OCR noise and word shuffle augmentations."""
    augmented = apply_augmentations(rows)
    combined = rows + augmented
    print(f"  Augment: {len(rows)} + {len(augmented)} = {len(combined)}")
    return combined


def stratified_split(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Stratified split: hold out TEST_SAMPLES_PER_CLASS per class for test."""
    by_label: dict[str, list[dict]] = {}
    for r in rows:
        by_label.setdefault(r["label"], []).append(r)

    test_set = []
    train_val_set = []

    for label, samples in sorted(by_label.items()):
        if len(samples) <= TEST_SAMPLES_PER_CLASS:
            print(f"  WARNING: Only {len(samples)} for {label}, using all as train")
            train_val_set.extend(samples)
            continue

        random.shuffle(samples)
        test_set.extend(samples[:TEST_SAMPLES_PER_CLASS])
        train_val_set.extend(samples[TEST_SAMPLES_PER_CLASS:])

    random.shuffle(test_set)
    random.shuffle(train_val_set)

    # Split train_val into train and val (stratified)
    train_labels = [r["label"] for r in train_val_set]
    train_idx, val_idx = train_test_split(
        range(len(train_val_set)),
        test_size=VAL_SPLIT,
        random_state=RANDOM_SEED,
        stratify=train_labels,
    )
    train_set = [train_val_set[i] for i in train_idx]
    val_set = [train_val_set[i] for i in val_idx]

    print(f"  Split: train={len(train_set)}, val={len(val_set)}, test={len(test_set)}")
    return train_set, val_set, test_set


def write_csv(rows: list[dict], path: Path):
    fieldnames = ["text", "label", "label_id", "language_variant", "language_id", "is_synthetic"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Written: {path} ({len(rows)} rows)")


def print_statistics(train: list[dict], val: list[dict], test: list[dict]):
    print(f"\n{'='*60}")
    print("DATASET STATISTICS")
    print(f"{'='*60}")

    for split_name, split_data in [("Train", train), ("Val", val), ("Test", test)]:
        print(f"\n--- {split_name} ({len(split_data)} samples) ---")
        label_counts = Counter(r["label"] for r in split_data)
        lang_counts = Counter(r["language_variant"] for r in split_data)
        avg_len = sum(len(r["text"].split()) for r in split_data) / max(len(split_data), 1)

        print(f"  Avg text length: {avg_len:.1f} words")
        print(f"  Class distribution:")
        for label in sorted(CLASSES.values()):
            print(f"    {label:35s} {label_counts.get(label, 0):5d}")
        print(f"  Language distribution:")
        for lang, count in lang_counts.most_common():
            print(f"    {lang:30s} {count:5d}")

    total = len(train) + len(val) + len(test)
    print(f"\nTotal dataset: {total} samples")

    stats = {
        "total": total,
        "train": len(train),
        "val": len(val),
        "test": len(test),
        "per_class_test": TEST_SAMPLES_PER_CLASS,
        "val_split": VAL_SPLIT,
    }
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"\nStats saved to: {STATS_FILE}")


def upload_to_hub(train: list[dict], val: list[dict], test: list[dict]):
    """Upload dataset to HuggingFace Hub."""
    try:
        from datasets import Dataset, DatasetDict, concatenate_datasets
        from huggingface_hub import HfApi
    except ImportError:
        print("  datasets/huggingface_hub not installed. Skipping upload.")
        return

    hf_token = os.getenv("HF_TOKEN") or os.getenv("HF_API_KEY")
    if not hf_token:
        print("  HF_TOKEN/HF_API_KEY not set. Skipping HuggingFace upload.")
        return

    repo_id = "meet136/indian-gst-transaction-classification"
    print(f"\n  Uploading to HuggingFace: {repo_id}")

    def _to_dataset(rows: list[dict]):
        texts = [r["text"] for r in rows]
        labels = [CLASS_TO_ID[r["label"]] for r in rows]
        label_names = [r["label"] for r in rows]
        langs = [r["language_variant"] for r in rows]
        synths = [True for _ in rows]

        data = {
            "text": texts,
            "label": labels,
            "label_name": label_names,
            "language_variant": langs,
            "is_synthetic": synths,
        }
        return Dataset.from_dict(data)

    train_ds = _to_dataset(train)
    val_ds = _to_dataset(val)
    test_ds = _to_dataset(test)

    dataset = DatasetDict({
        "train": train_ds,
        "validation": val_ds,
        "test": test_ds,
    })

    dataset.push_to_hub(repo_id, token=hf_token, private=False)
    print(f"  ✅ Uploaded to https://huggingface.co/datasets/{repo_id}")


def main():
    print("=" * 60)
    print("GST DATASET PREPARATION")
    print("=" * 60)

    # 1. Load
    print("\n[1/5] Loading raw data...")
    raw = load_raw(RAW_FILE)
    print(f"  Loaded {len(raw)} raw samples")

    # 2. Clean
    print("\n[2/5] Cleaning...")
    cleaned = clean(raw)

    # 3. Augment
    print("\n[3/5] Augmenting...")
    augmented = augment(cleaned)

    # 4. Split
    print("\n[4/5] Stratified splitting...")
    train, val, test = stratified_split(augmented)

    # 5. Write
    print("\n[5/5] Writing splits...")
    write_csv(train, TRAIN_FILE)
    write_csv(val, VAL_FILE)
    write_csv(test, TEST_FILE)

    # Statistics
    print_statistics(train, val, test)

    # Upload to HuggingFace
    print("\nUploading to HuggingFace Hub...")
    upload_to_hub(train, val, test)

    print(f"\n{'='*60}")
    print("Done! Ready for training.")
    print(f"  Train: {TRAIN_FILE}")
    print(f"  Val:   {VAL_FILE}")
    print(f"  Test:  {TEST_FILE}")


if __name__ == "__main__":
    main()

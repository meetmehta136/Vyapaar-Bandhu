import csv
rows = list(csv.DictReader(open("ml/data/raw_synthetic.csv", encoding="utf-8")))
print("=== CODE-MIXED SAMPLES (likely DeepSeek) ===")
count = 0
for r in rows:
    if r["language_variant"] == "Code-mixed Hindi-English" and count < 20:
        print(f'  {r["label"][:25]:25s} | {r["text"][:90]}')
        count += 1
print("\n=== GUJARATI SAMPLES ===")
count = 0
for r in rows:
    if r["language_variant"] == "Gujarati" and count < 10:
        print(f'  {r["label"][:25]:25s} | {r["text"][:90]}')
        count += 1
print("\n=== HINDI (DEVANAGARI) SAMPLES ===")
count = 0
for r in rows:
    if r["language_variant"] == "Hindi (Devanagari)" and count < 10:
        print(f'  {r["label"][:25]:25s} | {r["text"][:90]}')
        count += 1

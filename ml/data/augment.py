"""Data augmentation for GST transaction descriptions.

Strategies:
1. OCR noise injection — replace 5% characters with visually similar ones (10% of samples)
2. Word shuffle — shuffle word order in descriptions > 5 words (15% of samples)
3. Back-translation stub — ready for Google Translate API integration
"""

import random

# OCR confusion pairs: visually similar characters
OCR_NOISE_MAP = {
    "0": "O", "O": "0",
    "1": "l", "l": "1",
    "5": "S", "S": "5",
    "8": "B", "B": "8",
    "6": "G", "G": "6",
    "9": "q", "q": "9",
    "n": "h", "h": "n",
    "m": "rn", "rn": "m",
    "c": "e", "e": "c",
    "i": "j", "j": "i",
}


def inject_ocr_noise(text: str, noise_prob: float = 0.05) -> str:
    """Randomly replace characters with visually similar ones."""
    chars = list(text)
    for i in range(len(chars)):
        if random.random() < noise_prob and chars[i] in OCR_NOISE_MAP:
            chars[i] = OCR_NOISE_MAP[chars[i]]
    return "".join(chars)


def shuffle_words(text: str) -> str:
    """Shuffle word order in descriptions longer than 5 words."""
    words = text.split()
    if len(words) > 5:
        random.shuffle(words)
        return " ".join(words)
    return text


def apply_augmentations(rows: list[dict], ocr_prob: float = 0.10, shuffle_prob: float = 0.15) -> list[dict]:
    """Apply augmentations to a subset of rows."""
    augmented = []
    for row in rows:
        text = row["text"]
        # OCR noise injection
        if random.random() < ocr_prob:
            aug_text = inject_ocr_noise(text)
            aug_row = dict(row)
            aug_row["text"] = aug_text
            aug_row["is_synthetic"] = True
            augmented.append(aug_row)

        # Word shuffle
        if random.random() < shuffle_prob:
            aug_text = shuffle_words(text)
            if aug_text != text:
                aug_row = dict(row)
                aug_row["text"] = aug_text
                aug_row["is_synthetic"] = True
                augmented.append(aug_row)

    return augmented


# Back-translation stub (for future use with Google Translate API)
"""
def back_translate(text: str, source_lang: str = "hi", target_lang: str = "en") -> str:
    # Requires: pip install google-cloud-translate
    # Uses Google Translate API free tier
    # Step 1: Translate to English
    # Step 2: Translate back to source language
    # This introduces natural paraphrasing
    pass
"""

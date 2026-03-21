import re
from itertools import product

STATE_CODES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh",
    "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana",
    "07": "Delhi", "08": "Rajasthan",
    "09": "Uttar Pradesh", "10": "Bihar",
    "11": "Sikkim", "12": "Arunachal Pradesh",
    "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura",
    "17": "Meghalaya", "18": "Assam",
    "19": "West Bengal", "20": "Jharkhand",
    "21": "Odisha", "22": "Chhattisgarh",
    "23": "Madhya Pradesh", "24": "Gujarat",
    "25": "Daman & Diu", "26": "Dadra & Nagar Haveli",
    "27": "Maharashtra", "28": "Andhra Pradesh",
    "29": "Karnataka", "30": "Goa",
    "31": "Lakshadweep", "32": "Kerala",
    "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman & Nicobar", "36": "Telangana",
    "37": "Andhra Pradesh (New)",
}

# Modulo 36 charset — same as GSTN uses
CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Common OCR optical illusions
OCR_CONFUSIONS = {
    "1": ["I", "L"],
    "I": ["1", "L"],
    "L": ["1", "I"],
    "0": ["O", "D"],
    "O": ["0", "D"],
    "5": ["S"],
    "S": ["5"],
    "8": ["B"],
    "B": ["8"],
    "2": ["Z"],
    "Z": ["2"],
    "6": ["G"],
    "G": ["6"],
}

GSTIN_PATTERN = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'


def _modulo36_checksum(gstin_14: str) -> str:
    """Calculate the 15th check digit using GSTN Modulo 36 algorithm."""
    factor = 2
    total = 0
    for char in reversed(gstin_14):
        digit = CHARSET.index(char)
        val = factor * digit
        total += (val // 36) + (val % 36)
        factor = 3 if factor == 2 else 2
    remainder = total % 36
    check = (36 - remainder) % 36
    return CHARSET[check]


def _verify_checksum(gstin: str) -> bool:
    """Verify a full 15-char GSTIN using Modulo 36 checksum."""
    if len(gstin) != 15:
        return False
    try:
        expected = _modulo36_checksum(gstin[:14])
        return gstin[14] == expected
    except Exception:
        return False


def _auto_correct_gstin(raw: str) -> dict:
    """
    Try to auto-correct OCR mistakes using common optical illusions.
    Returns corrected GSTIN if found, else None.
    Max permutations capped at 512 to prevent timeout.
    """
    raw = raw.upper().strip()

    # Find positions with possible OCR confusions
    confused_positions = []
    for i, char in enumerate(raw):
        if char in OCR_CONFUSIONS:
            confused_positions.append((i, [char] + OCR_CONFUSIONS[char]))

    if not confused_positions:
        return {"corrected": None, "corrections": []}

    # Cap at 9 positions to prevent combinatorial explosion
    confused_positions = confused_positions[:9]

    positions = [p[0] for p in confused_positions]
    options = [p[1] for p in confused_positions]

    for combo in product(*options):
        candidate = list(raw)
        for pos, char in zip(positions, combo):
            candidate[pos] = char
        candidate_str = "".join(candidate)

        # Must be 15 chars and match pattern
        if len(candidate_str) != 15:
            continue
        if not re.match(GSTIN_PATTERN, candidate_str):
            continue
        if candidate_str[:2] not in STATE_CODES:
            continue
        if _verify_checksum(candidate_str):
            corrections = []
            for pos, orig, new in zip(positions, [raw[p] for p in positions], combo):
                if orig != new:
                    corrections.append(f"Position {pos+1}: '{orig}' → '{new}'")
            return {"corrected": candidate_str, "corrections": corrections}

    return {"corrected": None, "corrections": []}


def validate_gstin(gstin: str) -> dict:
    if not gstin:
        return {"is_valid": False, "error": "GSTIN is empty", "auto_corrected": False}

    gstin = gstin.upper().strip()

    if len(gstin) != 15:
        return {
            "is_valid": False,
            "error": f"GSTIN must be 15 characters, got {len(gstin)}",
            "auto_corrected": False
        }

    # Check pattern
    if not re.match(GSTIN_PATTERN, gstin):
        # Try auto-correction before giving up
        result = _auto_correct_gstin(gstin)
        if result["corrected"]:
            corrected = result["corrected"]
            state_code = corrected[:2]
            return {
                "is_valid": True,
                "gstin": corrected,
                "original_gstin": gstin,
                "state_code": state_code,
                "state_name": STATE_CODES.get(state_code, "Unknown"),
                "pan": corrected[2:12],
                "auto_corrected": True,
                "corrections": result["corrections"],
                "error": None,
                "note": f"Auto-corrected OCR mistake: {', '.join(result['corrections'])}"
            }
        return {
            "is_valid": False,
            "error": "GSTIN format is invalid and could not be auto-corrected",
            "auto_corrected": False
        }

    state_code = gstin[:2]
    if state_code not in STATE_CODES:
        return {
            "is_valid": False,
            "error": f"Invalid state code: {state_code}",
            "auto_corrected": False
        }

    # Verify checksum
    if not _verify_checksum(gstin):
        # Try auto-correction
        result = _auto_correct_gstin(gstin)
        if result["corrected"]:
            corrected = result["corrected"]
            sc = corrected[:2]
            return {
                "is_valid": True,
                "gstin": corrected,
                "original_gstin": gstin,
                "state_code": sc,
                "state_name": STATE_CODES.get(sc, "Unknown"),
                "pan": corrected[2:12],
                "auto_corrected": True,
                "corrections": result["corrections"],
                "error": None,
                "note": f"Checksum failed — auto-corrected OCR mistake: {', '.join(result['corrections'])}"
            }
        return {
            "is_valid": False,
            "error": "GSTIN checksum validation failed — possible OCR error",
            "auto_corrected": False,
            "hint": "Common OCR mistakes: 1↔I, 0↔O, 5↔S, 8↔B"
        }

    return {
        "is_valid": True,
        "gstin": gstin,
        "state_code": state_code,
        "state_name": STATE_CODES[state_code],
        "pan": gstin[2:12],
        "auto_corrected": False,
        "error": None
    }
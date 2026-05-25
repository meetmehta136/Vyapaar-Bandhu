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

CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_PATTERN = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'

OCR_CONFUSIONS = {
   "1": ["I", "L"], "I": ["1", "L", "D"], "L": ["1", "I"],
   "0": ["O", "D"], "O": ["0", "D"], "D": ["0", "O", "I"],
    "5": ["S"], "S": ["5"],
    "8": ["B"], "B": ["8"],
    "2": ["Z"], "Z": ["2"],
    "6": ["G"], "G": ["6"],
    "4": ["A"], "A": ["4"],
}


def _modulo36_checksum(gstin_14: str) -> str:
    factor = 2
    total = 0
    for char in reversed(gstin_14):
        if char not in CHARSET:
            return "?"
        digit = CHARSET.index(char)
        val = factor * digit
        total += (val // 36) + (val % 36)
        factor = 3 if factor == 2 else 2
    remainder = total % 36
    check = (36 - remainder) % 36
    return CHARSET[check]


def _verify_checksum(gstin: str) -> bool:
    if len(gstin) != 15:
        return False
    try:
        return gstin[14] == _modulo36_checksum(gstin[:14])
    except Exception:
        return False


def _auto_correct_gstin(raw: str) -> dict:
    confused_positions = []
    for i, char in enumerate(raw):
        if char in OCR_CONFUSIONS:
            confused_positions.append((i, [char] + OCR_CONFUSIONS[char]))

    if not confused_positions:
        return {"corrected": None, "corrections": []}

    # Prioritize position 14 (checksum) — it's the most impactful to try
    confused_positions.sort(key=lambda x: x[0] != 14)
    confused_positions = confused_positions[:8]
    positions = [p[0] for p in confused_positions]
    options = [p[1] for p in confused_positions]
    originals = [raw[p] for p in positions]

    for combo in product(*options):
        candidate = list(raw)
        for pos, char in zip(positions, combo):
            candidate[pos] = char
        c = "".join(candidate)
        if len(c) != 15:
            continue
        if c[:2] not in STATE_CODES:
            continue
        if not re.match(GSTIN_PATTERN, c):
            continue
        if _verify_checksum(c):
            corrections = [f"pos {p+1}: '{o}'->'{n}'" for p, o, n in zip(positions, originals, combo) if o != n]
            return {"corrected": c, "corrections": corrections}

    return {"corrected": None, "corrections": []}


def validate_gstin(gstin: str) -> dict:
    if not gstin:
        return {"is_valid": False, "error": "GSTIN is empty", "auto_corrected": False}

    gstin = gstin.upper().strip()

    if len(gstin) != 15:
        return {"is_valid": False, "error": f"GSTIN must be 15 characters, got {len(gstin)}", "auto_corrected": False}

    pattern_ok = bool(re.match(GSTIN_PATTERN, gstin))
    state_ok = gstin[:2] in STATE_CODES
    checksum_ok = _verify_checksum(gstin) if pattern_ok and state_ok else False

    if pattern_ok and state_ok and checksum_ok:
        return {"is_valid": True, "gstin": gstin, "state_code": gstin[:2], "state_name": STATE_CODES[gstin[:2]], "pan": gstin[2:12], "auto_corrected": False, "error": None}

    # Try auto-correction
    result = _auto_correct_gstin(gstin)
    if result["corrected"]:
        c = result["corrected"]
        sc = c[:2]
        return {"is_valid": True, "gstin": c, "original_gstin": gstin, "state_code": sc, "state_name": STATE_CODES.get(sc, "Unknown"), "pan": c[2:12], "auto_corrected": True, "corrections": result["corrections"], "error": None, "note": f"Auto-corrected: {', '.join(result['corrections'])}"}

    if not pattern_ok:
        return {"is_valid": False, "error": "GSTIN format invalid — could not auto-correct", "auto_corrected": False, "hint": "Common OCR errors: 1<->I, 0<->O, 5<->S, 8<->B"}
    if not state_ok:
        return {"is_valid": False, "error": f"Invalid state code: {gstin[:2]}", "auto_corrected": False}
    return {"is_valid": False, "error": "Checksum failed — OCR error not correctable", "auto_corrected": False}
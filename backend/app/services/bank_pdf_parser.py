import re
from datetime import datetime
from typing import Optional
from loguru import logger

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


# ─── BANK DETECTION ──────────────────────────────────────────────────
def detect_bank(text: str) -> str:
    text_lower = text.lower()
    if "hdfc bank" in text_lower or "hdfcbank" in text_lower:
        return "HDFC"
    elif "state bank of india" in text_lower or "sbi" in text_lower:
        return "SBI"
    elif "icici bank" in text_lower:
        return "ICICI"
    elif "axis bank" in text_lower:
        return "AXIS"
    elif "kotak mahindra" in text_lower or "kotak bank" in text_lower:
        return "KOTAK"
    else:
        return "GENERIC"


# ─── AMOUNT CLEANER ───────────────────────────────────────────────────
def clean_amount(amount_str: str) -> Optional[float]:
    if not amount_str:
        return None
    cleaned = re.sub(r"[₹,\s]", "", str(amount_str))
    cleaned = cleaned.replace("Dr", "").replace("Cr", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


# ─── HDFC PARSER ──────────────────────────────────────────────────────
def parse_hdfc(text: str, tables: list) -> list:
    transactions = []

    # HDFC format: Date | Narration | Chq/Ref | Value Date | Withdrawal | Deposit | Balance
    date_pattern = r"(\d{2}/\d{2}/\d{2,4})"
    amount_pattern = r"[\d,]+\.\d{2}"

    for table in tables:
        if not table:
            continue
        for row in table:
            if not row or len(row) < 5:
                continue
            row = [str(c).strip() if c else "" for c in row]

            # Check if first col looks like a date
            if not re.match(date_pattern, row[0]):
                continue

            try:
                date_str = row[0]
                narration = row[1] if len(row) > 1 else ""
                withdrawal = clean_amount(row[4]) if len(row) > 4 else None
                deposit = clean_amount(row[5]) if len(row) > 5 else None
                balance = clean_amount(row[6]) if len(row) > 6 else None

                if not narration or narration.lower() in ["narration", "description"]:
                    continue

                transactions.append({
                    "date": date_str,
                    "description": narration,
                    "debit": withdrawal,
                    "credit": deposit,
                    "balance": balance,
                    "type": "debit" if withdrawal else "credit",
                    "amount": withdrawal or deposit or 0,
                    "bank": "HDFC"
                })
            except Exception:
                continue

    return transactions


# ─── SBI PARSER ───────────────────────────────────────────────────────
def parse_sbi(text: str, tables: list) -> list:
    transactions = []

    # SBI format: Txn Date | Value Date | Description | Ref No | Debit | Credit | Balance
    date_pattern = r"(\d{2} \w{3} \d{4}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4})"

    for table in tables:
        if not table:
            continue
        for row in table:
            if not row or len(row) < 5:
                continue
            row = [str(c).strip() if c else "" for c in row]

            if not re.match(date_pattern, row[0]):
                continue

            try:
                date_str = row[0]
                description = row[2] if len(row) > 2 else ""
                debit = clean_amount(row[4]) if len(row) > 4 else None
                credit = clean_amount(row[5]) if len(row) > 5 else None
                balance = clean_amount(row[6]) if len(row) > 6 else None

                if not description or description.lower() in ["description", "particulars"]:
                    continue

                transactions.append({
                    "date": date_str,
                    "description": description,
                    "debit": debit,
                    "credit": credit,
                    "balance": balance,
                    "type": "debit" if debit else "credit",
                    "amount": debit or credit or 0,
                    "bank": "SBI"
                })
            except Exception:
                continue

    return transactions


# ─── ICICI PARSER ─────────────────────────────────────────────────────
def parse_icici(text: str, tables: list) -> list:
    transactions = []

    # ICICI format: S No | Value Date | Transaction Date | Cheque | Description | Dr | Cr | Balance
    date_pattern = r"(\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4})"

    for table in tables:
        if not table:
            continue
        for row in table:
            if not row or len(row) < 6:
                continue
            row = [str(c).strip() if c else "" for c in row]

            # ICICI has date in col 1 or 2
            date_col = None
            for i in [1, 2]:
                if i < len(row) and re.match(date_pattern, row[i]):
                    date_col = i
                    break

            if date_col is None:
                continue

            try:
                date_str = row[date_col]
                description = row[4] if len(row) > 4 else ""
                debit = clean_amount(row[5]) if len(row) > 5 else None
                credit = clean_amount(row[6]) if len(row) > 6 else None
                balance = clean_amount(row[7]) if len(row) > 7 else None

                if not description or description.lower() in ["description", "particulars"]:
                    continue

                transactions.append({
                    "date": date_str,
                    "description": description,
                    "debit": debit,
                    "credit": credit,
                    "balance": balance,
                    "type": "debit" if debit else "credit",
                    "amount": debit or credit or 0,
                    "bank": "ICICI"
                })
            except Exception:
                continue

    return transactions


# ─── AXIS PARSER ──────────────────────────────────────────────────────
def parse_axis(text: str, tables: list) -> list:
    transactions = []

    date_pattern = r"(\d{2}-\d{2}-\d{4}|\d{2}/\d{2}/\d{4})"

    for table in tables:
        if not table:
            continue
        for row in table:
            if not row or len(row) < 5:
                continue
            row = [str(c).strip() if c else "" for c in row]

            if not re.match(date_pattern, row[0]):
                continue

            try:
                date_str = row[0]
                description = row[1] if len(row) > 1 else ""
                debit = clean_amount(row[3]) if len(row) > 3 else None
                credit = clean_amount(row[4]) if len(row) > 4 else None
                balance = clean_amount(row[5]) if len(row) > 5 else None

                if not description or description.lower() in ["description", "particulars"]:
                    continue

                transactions.append({
                    "date": date_str,
                    "description": description,
                    "debit": debit,
                    "credit": credit,
                    "balance": balance,
                    "type": "debit" if debit else "credit",
                    "amount": debit or credit or 0,
                    "bank": "AXIS"
                })
            except Exception:
                continue

    return transactions


# ─── KOTAK PARSER ─────────────────────────────────────────────────────
def parse_kotak(text: str, tables: list) -> list:
    transactions = []

    date_pattern = r"(\d{2}-\d{2}-\d{4}|\d{2}/\d{2}/\d{4})"

    for table in tables:
        if not table:
            continue
        for row in table:
            if not row or len(row) < 5:
                continue
            row = [str(c).strip() if c else "" for c in row]

            if not re.match(date_pattern, row[0]):
                continue

            try:
                date_str = row[0]
                description = row[1] if len(row) > 1 else ""
                debit = clean_amount(row[2]) if len(row) > 2 else None
                credit = clean_amount(row[3]) if len(row) > 3 else None
                balance = clean_amount(row[4]) if len(row) > 4 else None

                if not description or description.lower() in ["description", "particulars"]:
                    continue

                transactions.append({
                    "date": date_str,
                    "description": description,
                    "debit": debit,
                    "credit": credit,
                    "balance": balance,
                    "type": "debit" if debit else "credit",
                    "amount": debit or credit or 0,
                    "bank": "KOTAK"
                })
            except Exception:
                continue

    return transactions


# ─── GENERIC PARSER (fallback) ────────────────────────────────────────
def parse_generic(text: str, tables: list) -> list:
    transactions = []
    date_pattern = r"(\d{2}[-/]\d{2}[-/]\d{2,4}|\d{2} \w{3} \d{4})"

    for table in tables:
        if not table:
            continue
        for row in table:
            if not row or len(row) < 3:
                continue
            row = [str(c).strip() if c else "" for c in row]

            date_found = None
            for cell in row[:3]:
                if re.match(date_pattern, cell):
                    date_found = cell
                    break

            if not date_found:
                continue

            amounts = []
            for cell in row:
                amt = clean_amount(cell)
                if amt and amt > 0:
                    amounts.append(amt)

            if not amounts:
                continue

            description = " ".join([c for c in row[1:4] if c and not re.match(date_pattern, c)])

            transactions.append({
                "date": date_found,
                "description": description[:100],
                "debit": amounts[0] if len(amounts) > 0 else None,
                "credit": amounts[1] if len(amounts) > 1 else None,
                "balance": amounts[-1] if len(amounts) > 2 else None,
                "type": "debit",
                "amount": amounts[0] if amounts else 0,
                "bank": "GENERIC"
            })

    return transactions


# ─── GST KEYWORD CLASSIFIER ───────────────────────────────────────────
def classify_transaction_gst(description: str) -> dict:
    desc = description.lower()

    gst_keywords = {
        "purchase": ["purchase", "bought", "bill", "invoice", "vendor", "supplier"],
        "salary":   ["salary", "wages", "payroll", "staff", "employee"],
        "rent":     ["rent", "lease", "property"],
        "utility":  ["electricity", "water", "internet", "telephone", "broadband"],
        "travel":   ["travel", "flight", "train", "hotel", "uber", "ola", "cab"],
        "food":     ["restaurant", "food", "lunch", "dinner", "swiggy", "zomato"],
        "bank":     ["neft", "rtgs", "imps", "transfer", "upi", "atm", "cash"],
        "tax":      ["gst", "tds", "tax", "income tax", "advance tax"],
    }

    for category, keywords in gst_keywords.items():
        if any(kw in desc for kw in keywords):
            itc_eligible = category in ["purchase", "utility", "rent"]
            return {
                "category": category,
                "itc_possible": itc_eligible,
                "needs_invoice": itc_eligible
            }

    return {
        "category": "other",
        "itc_possible": False,
        "needs_invoice": False
    }


# ─── MAIN PARSER FUNCTION ─────────────────────────────────────────────
def parse_bank_statement(pdf_path: str) -> dict:
    if pdfplumber is None:
        return {
            "success": False,
            "error": "pdfplumber not installed. Run: pip install pdfplumber",
            "transactions": []
        }

    try:
        all_text = ""
        all_tables = []

        with pdfplumber.open(pdf_path) as pdf:
            logger.info(f"PDF pages: {len(pdf.pages)}")
            for page in pdf.pages:
                text = page.extract_text() or ""
                all_text += text + "\n"
                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)

        if not all_text.strip():
            return {
                "success": False,
                "error": "Could not extract text from PDF. May be scanned/image PDF.",
                "transactions": []
            }

        bank = detect_bank(all_text)
        logger.info(f"Detected bank: {bank}")

        parsers = {
            "HDFC":    parse_hdfc,
            "SBI":     parse_sbi,
            "ICICI":   parse_icici,
            "AXIS":    parse_axis,
            "KOTAK":   parse_kotak,
            "GENERIC": parse_generic,
        }

        parser = parsers.get(bank, parse_generic)
        transactions = parser(all_text, all_tables)

        # Fallback to generic if bank parser found nothing
        if not transactions and bank != "GENERIC":
            logger.warning(f"{bank} parser found nothing, trying generic...")
            transactions = parse_generic(all_text, all_tables)

        # Classify each transaction for GST relevance
        for txn in transactions:
            gst_info = classify_transaction_gst(txn["description"])
            txn.update(gst_info)

        # Summary stats
        total_debit  = sum(t["debit"] or 0 for t in transactions)
        total_credit = sum(t["credit"] or 0 for t in transactions)
        itc_possible = [t for t in transactions if t.get("itc_possible")]

        logger.info(f"Parsed {len(transactions)} transactions")
        logger.info(f"Total debit: Rs.{total_debit:,.2f} | credit: Rs.{total_credit:,.2f}")
        logger.info(f"ITC possible on {len(itc_possible)} transactions")

        return {
            "success": True,
            "bank": bank,
            "total_transactions": len(transactions),
            "total_debit": round(total_debit, 2),
            "total_credit": round(total_credit, 2),
            "itc_possible_count": len(itc_possible),
            "transactions": transactions,
            "summary": {
                "purchase_count": len([t for t in transactions if t.get("category") == "purchase"]),
                "salary_count":   len([t for t in transactions if t.get("category") == "salary"]),
                "travel_count":   len([t for t in transactions if t.get("category") == "travel"]),
                "food_count":     len([t for t in transactions if t.get("category") == "food"]),
            }
        }

    except Exception as e:
        logger.error(f"PDF parsing error: {e}")
        return {
            "success": False,
            "error": str(e),
            "transactions": []
        }


# ─── WHATSAPP FLOW ────────────────────────────────────────────────────
def parse_bank_statement_from_bytes(pdf_bytes: bytes, filename: str = "statement.pdf") -> dict:
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        result = parse_bank_statement(tmp_path)
        return result
    finally:
        os.unlink(tmp_path)
"""
Shared parsing utilities for bank statement PDFs and Tithe.ly Excel/CSV files.
Returns a list of standardized transaction dicts for preview and import.
"""
import re
import math
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def build_member_index(members):
    """Returns {normalized_name: member} dict for fast fuzzy lookup."""
    idx = {}
    for m in members:
        idx[normalize_name(f"{m.first_name} {m.last_name}")] = m
        idx[normalize_name(f"{m.last_name} {m.first_name}")] = m
    return idx


def match_member(raw_name: str, index: dict):
    """Fuzzy match a raw bank/tithe.ly name to a member."""
    clean = re.sub(r"\s+(Ref|on|Payment|Annual|Yearly|Zelle|From).*", "", raw_name, flags=re.I).strip()
    norm = normalize_name(clean)
    if norm in index:
        return index[norm]

    words = [w for w in re.split(r"\s+", clean.lower()) if len(w) > 2]
    best, best_score = None, 0
    seen_members = set()
    for member in index.values():
        if id(member) in seen_members:
            continue
        seen_members.add(id(member))
        fn = normalize_name(member.first_name)
        ln = normalize_name(member.last_name)
        score = 0
        for w in words:
            wn = normalize_name(w)
            if fn.startswith(wn[:4]) or wn.startswith(fn[:4]):
                score += 2
            if ln.startswith(wn[:4]) or wn.startswith(ln[:4]):
                score += 2
        if score >= 4 and score > best_score:
            best_score = score
            best = member
    return best


def _parse_amount(val) -> int:
    """Convert a dollar string/number to cents int."""
    if val is None:
        return 0
    try:
        return int(Decimal(str(val).replace(",", "").replace("$", "").strip()) * 100)
    except InvalidOperation:
        return 0


def _parse_date(val) -> date | None:
    if not val:
        return None
    if isinstance(val, (date, datetime)):
        return val.date() if isinstance(val, datetime) else val
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%-m/%-d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


# ── Wells Fargo PDF ────────────────────────────────────────────────────────────

def parse_wells_fargo_pdf(file_bytes: bytes) -> list[dict]:
    """
    Extract Zelle/check transactions from a Wells Fargo bank statement PDF.
    Returns list of raw transaction dicts.
    """
    import pdfplumber

    transactions = []
    date_pattern = re.compile(r"^(\d{1,2}/\d{1,2})\s+(.+)")
    amount_pattern = re.compile(r"-?\$?([\d,]+\.\d{2})")

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split("\n")
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                m = date_pattern.match(line)
                if m:
                    month_day = m.group(1)
                    rest = m.group(2).strip()
                    # Collect continuation lines
                    j = i + 1
                    while j < len(lines) and not date_pattern.match(lines[j].strip()):
                        rest += " " + lines[j].strip()
                        j += 1

                    amounts = amount_pattern.findall(rest)
                    if not amounts:
                        i = j
                        continue

                    # Last amount is typically the running balance; second-to-last is the transaction
                    try:
                        txn_amount = float(amounts[-2].replace(",", "")) if len(amounts) >= 2 else float(amounts[-1].replace(",", ""))
                    except (ValueError, IndexError):
                        i = j
                        continue

                    amount_cents = int(round(txn_amount * 100))
                    desc = re.sub(r"\s+\$?[\d,]+\.\d{2}", "", rest).strip()

                    # Classify
                    is_zelle_in = bool(re.search(r"zelle.*from|from.*zelle", desc, re.I))
                    is_zelle_out = bool(re.search(r"zelle.*to|to.*zelle|zelle sent", desc, re.I))
                    is_check_out = bool(re.search(r"check\s*#?\s*\d+", desc, re.I))
                    is_tithe = bool(re.search(r"tithe\.?ly|tithely", desc, re.I))

                    if is_zelle_in or is_tithe:
                        txn_type = "tithe_ly" if is_tithe else "member_payment"
                        credit = txn_amount
                        debit = 0.0
                    elif is_zelle_out or is_check_out:
                        txn_type = "check_out"
                        credit = 0.0
                        debit = txn_amount
                    else:
                        i = j
                        continue

                    # Extract member name from Zelle description
                    member_name = ""
                    zelle_name = re.search(r"(?:zelle from|from)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)+)", desc, re.I)
                    if zelle_name:
                        member_name = zelle_name.group(1).strip()

                    transactions.append({
                        "raw_date": month_day,
                        "description": desc,
                        "member_name": member_name,
                        "credit": credit,
                        "debit": debit,
                        "amount_cents": amount_cents,
                        "txn_type": txn_type,
                        "reference": "",
                    })
                    i = j
                else:
                    i += 1

    return transactions


# ── Tithe.ly Excel / CSV ──────────────────────────────────────────────────────

def parse_tithely_excel(file_bytes: bytes, filename: str) -> list[dict]:
    """
    Parse a Tithe.ly contribution export (Excel .xlsx or .csv).
    Expected columns (flexible): First Name, Last Name, Amount, Date,
    Payment Method, Check / Transaction Number, Note/Fund Name.
    """
    rows = []

    if filename.lower().endswith((".xlsx", ".xls")):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        ws = wb.active
        headers = None
        for row in ws.iter_rows(values_only=True):
            if headers is None:
                headers = [str(c).strip() if c else "" for c in row]
                continue
            rows.append(dict(zip(headers, [c for c in row])))
    else:
        import csv as _csv
        text = file_bytes.decode("utf-8-sig", errors="replace")
        reader = _csv.DictReader(io.StringIO(text))
        rows = list(reader)

    transactions = []
    for row in rows:
        # Flexible column name matching
        first = _get(row, "First Name", "first_name", "FirstName", "first")
        last = _get(row, "Last Name", "last_name", "LastName", "last")
        amount_raw = _get(row, "Amount", "amount", "Total", "total")
        date_raw = _get(row, "Date", "date", "Payment Date", "payment_date")
        method_raw = _get(row, "Payment Method", "method", "Method")
        ref_raw = _get(row, "Check / Transaction Number", "Transaction Number", "Reference", "reference", "Check Number")
        note_raw = _get(row, "Note", "Notes", "Fund Name", "notes")

        amount_cents = _parse_amount(amount_raw)
        txn_date = _parse_date(date_raw)

        if not amount_cents or not txn_date:
            continue

        first = str(first or "").strip()
        last = str(last or "").strip()
        member_name = f"{first} {last}".strip()
        method = str(method_raw or "").strip().lower()
        if "check" in method:
            method = "check"
        elif "cash" in method:
            method = "cash"
        elif "ach" in method or "bank" in method:
            method = "bank_transfer"
        else:
            method = "online"

        transactions.append({
            "raw_date": str(txn_date),
            "description": str(note_raw or "Tithe.ly"),
            "member_name": member_name,
            "credit": amount_cents / 100,
            "debit": 0.0,
            "amount_cents": amount_cents,
            "txn_type": "tithe_ly",
            "reference": str(ref_raw or "").strip(),
            "pay_date": txn_date,
            "method": method,
        })

    return transactions


def _get(row: dict, *keys):
    """Return first matching key value from a dict (case-insensitive fallback)."""
    for k in keys:
        if k in row:
            return row[k]
    lower_row = {str(rk).lower(): rv for rk, rv in row.items()}
    for k in keys:
        if k.lower() in lower_row:
            return lower_row[k.lower()]
    return None


# ── Normalize to preview rows ─────────────────────────────────────────────────

def build_preview(transactions: list[dict], members, org) -> list[dict]:
    """
    Match transactions against members and return preview rows.
    Each row has: status (matched/unmatched/duplicate), member info, amount, date, etc.
    """
    from apps.obligations.models import Payment

    index = build_member_index(members)
    preview = []

    for i, txn in enumerate(transactions):
        raw_date = txn.get("pay_date") or txn.get("raw_date", "")
        if isinstance(raw_date, str):
            pay_date = _parse_date(raw_date)
        else:
            pay_date = raw_date

        if not pay_date or not txn.get("amount_cents", 0):
            continue

        amount_cents = txn["amount_cents"]
        member_name = txn.get("member_name", "")
        txn_type = txn.get("txn_type", "member_payment")

        member = None
        if member_name and member_name.strip() not in ("", "Tithe.ly Batch"):
            member = match_member(member_name, index)

        # Duplicate check
        duplicate = False
        if member:
            duplicate = Payment.objects.filter(
                organization=org,
                member=member,
                amount_cents=amount_cents,
                payment_date=pay_date,
            ).exists()

        status = "duplicate" if duplicate else ("matched" if member else "unmatched")

        preview.append({
            "idx": i,
            "txn_type": txn_type,
            "date": str(pay_date),
            "member_name": member_name,
            "matched_member_id": str(member.id) if member else None,
            "matched_member_name": member.get_full_name() if member else None,
            "amount_cents": amount_cents,
            "credit": txn.get("credit", amount_cents / 100),
            "debit": txn.get("debit", 0),
            "description": txn.get("description", ""),
            "reference": txn.get("reference", ""),
            "method": txn.get("method", "other"),
            "status": status,
            "include": status == "matched",  # default: include matched, skip others
        })

    return preview

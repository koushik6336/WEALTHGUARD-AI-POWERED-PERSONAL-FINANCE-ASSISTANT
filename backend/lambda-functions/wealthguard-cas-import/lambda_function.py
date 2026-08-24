import os
import json
import pg8000
import base64
import io
import re
import sys

sys.path.insert(0, '/var/task')

RDS_HOST = "wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com"
RDS_USER = "wealthguard_admin"
RDS_PASS = "os.environ.get("RDS_PASSWORD")"
RDS_DB = "wealthguard"
RDS_PORT = 5432

headers = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}

def get_conn():
    return pg8000.connect(RDS_USER, host=RDS_HOST, port=RDS_PORT, database=RDS_DB, password=RDS_PASS, ssl_context=True)

NUM = r'([\d,]+\.?\d*)'

UNITS_RE = re.compile(r'(?:Closing\s*Balance|Units?\s*(?:Held|Balance)?)\s*:?\s*' + NUM, re.IGNORECASE)
NAV_RE = re.compile(r'NAV\s*(?:\(Rs\.?\))?\s*:?\s*(?:Rs\.?)?\s*' + NUM, re.IGNORECASE)
VALUE_RE = re.compile(r'(?:Market\s*Value|Current\s*Value|Value|Total\s*Cost)\s*(?:\(Rs\.?\))?\s*:?\s*(?:Rs\.?)?\s*' + NUM, re.IGNORECASE)
COST_RE = re.compile(r'(?:Total\s*Cost|Amount\s*Invested|Cost\s*Value)\s*:?\s*(?:Rs\.?)?\s*' + NUM, re.IGNORECASE)
FOLIO_RE = re.compile(r'Folio\s*No\.?\s*:?\s*([\w\/\-]+)', re.IGNORECASE)
SCHEME_KEYWORDS = ['Fund', 'Scheme', 'ELSS']
CONTINUATION_KEYWORDS = ['Growth', 'Direct', 'Regular', 'Plan', 'Dividend', 'IDCW']
NOISE_PREFIXES = ('Folio', 'ISIN', 'Registrar', 'PAN', 'KYC', 'Nominee', 'Advisor', 'Total')


def to_float(s):
    if not s:
        return 0.0
    try:
        return float(s.replace(',', ''))
    except ValueError:
        return 0.0


def looks_like_scheme_start(line):
    if len(line) < 15 or len(line) > 150:
        return False
    if line.startswith(NOISE_PREFIXES):
        return False
    if not any(kw in line for kw in SCHEME_KEYWORDS):
        return False
    digit_ratio = sum(c.isdigit() for c in line) / max(len(line), 1)
    if digit_ratio > 0.3:
        return False
    return True


def looks_like_scheme_continuation(line):
    # short lines like "Direct Plan - Growth" that follow a scheme name line
    if len(line) < 3 or len(line) > 60:
        return False
    if line.startswith(NOISE_PREFIXES):
        return False
    digit_ratio = sum(c.isdigit() for c in line) / max(len(line), 1)
    if digit_ratio > 0.2:
        return False
    return any(kw in line for kw in CONTINUATION_KEYWORDS)


def parse_cas_pdf(pdf_bytes, password=None):
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    if reader.is_encrypted:
        if password:
            reader.decrypt(password)
        else:
            return None, "PDF is password protected. Please provide password."

    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"

    lines = [l.strip() for l in text.split('\n') if l.strip()]

    holdings = []
    current_scheme = None
    current_folio = None
    window_units = None
    window_nav = None
    window_value = None
    window_cost = None
    WINDOW_SIZE = 8
    lines_since_scheme = 0
    just_started_scheme = False

    def flush():
        nonlocal current_scheme, window_units, window_nav, window_value, window_cost, current_folio
        if current_scheme and window_units and window_units > 0:
            value = window_value if window_value else (window_units * (window_nav or 0))
            cost = window_cost if window_cost else value
            holdings.append({
                "scheme_name": current_scheme[:150],
                "folio": current_folio,
                "units_held": window_units,
                "nav": window_nav or (value / window_units if window_units else 0),
                "current_value": value,
                "amount_invested": cost,
            })
        current_scheme = None
        window_units = None
        window_nav = None
        window_value = None
        window_cost = None
        current_folio = None

    for line in lines:
        folio_match = FOLIO_RE.search(line)
        if folio_match:
            if current_scheme:
                flush()
            current_folio = folio_match.group(1)
            continue

        if looks_like_scheme_start(line):
            if current_scheme:
                flush()
            current_scheme = line
            lines_since_scheme = 0
            just_started_scheme = True
            continue

        # merge continuation lines (e.g. "Direct Plan - Growth") into the scheme name
        # instead of treating them as a brand new scheme
        if just_started_scheme and looks_like_scheme_continuation(line):
            current_scheme = f"{current_scheme} - {line}"
            just_started_scheme = False
            continue
        just_started_scheme = False

        if current_scheme:
            lines_since_scheme += 1
            if lines_since_scheme > WINDOW_SIZE:
                flush()
                continue

            u = UNITS_RE.search(line)
            n = NAV_RE.search(line)
            v = VALUE_RE.search(line)
            c = COST_RE.search(line)

            if u and window_units is None:
                window_units = to_float(u.group(1))
            if n and window_nav is None:
                window_nav = to_float(n.group(1))
            if v and window_value is None:
                window_value = to_float(v.group(1))
            if c and window_cost is None:
                window_cost = to_float(c.group(1))

    if current_scheme:
        flush()

    seen = set()
    deduped = []
    for h in holdings:
        key = (h["scheme_name"], h["folio"], round(h["units_held"], 4))
        if key not in seen:
            seen.add(key)
            deduped.append(h)

    return deduped, None


def lambda_handler(event, context):
    method = event.get("httpMethod", "POST")

    try:
        if method == "POST":
            body = json.loads(event.get("body") or "{}")
            user_id = body.get("user_id")
            pdf_base64 = body.get("pdf_base64")
            password = body.get("password", "")
            confirm = body.get("confirm", False)
            preview_data = body.get("preview_data")

            if not user_id or not pdf_base64:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "user_id and pdf_base64 required"})}

            if confirm and preview_data:
                conn = get_conn()
                conn.autocommit = True
                cur = conn.cursor()
                count = 0
                for h in preview_data:
                    cur.execute("""
                        INSERT INTO investments (user_id, scheme_name, units_held, current_value, amount_invested, investment_type, source, last_updated)
                        VALUES (%s, %s, %s, %s, %s, 'mutual_fund', 'CAS', NOW())
                    """, (user_id, h['scheme_name'], h.get('units_held', 0), h.get('current_value', 0), h.get('amount_invested', 0)))
                    count += 1
                conn.close()
                return {"statusCode": 200, "headers": headers, "body": json.dumps({"status": "imported", "count": count})}

            pdf_bytes = base64.b64decode(pdf_base64)
            holdings, error = parse_cas_pdf(pdf_bytes, password)

            if error:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": error})}

            if not holdings:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "No holdings found in PDF. Please ensure this is a valid CAS statement."})}

            return {"statusCode": 200, "headers": headers, "body": json.dumps({
                "status": "preview",
                "holdings": holdings,
                "count": len(holdings)
            })}

    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}

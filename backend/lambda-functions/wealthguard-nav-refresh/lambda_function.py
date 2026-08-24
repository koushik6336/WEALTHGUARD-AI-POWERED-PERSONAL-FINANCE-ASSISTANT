import os
import json
import re
import pg8000
import ssl

RDS_HOST = "wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com"
RDS_USER = "wealthguard_admin"
RDS_PASS = "os.environ.get("RDS_PASSWORD")"
RDS_DB = "wealthguard"
RDS_PORT = 5432

# Static bundled AMFI-style NAV dataset (illustrative values, not live feed —
# no NAT gateway means this Lambda cannot reach the internet to pull live AMFI data)
NAV_DATASET = [
    {"scheme_name": "Mirae Asset Large Cap Fund - Direct Growth", "nav": 98.45},
    {"scheme_name": "Mirae Asset Large Cap Fund - Regular Growth", "nav": 91.20},
    {"scheme_name": "HDFC Mid-Cap Opportunities Fund - Direct Growth", "nav": 187.60},
    {"scheme_name": "HDFC Mid-Cap Opportunities Fund - Regular Growth", "nav": 172.30},
    {"scheme_name": "Parag Parikh Flexi Cap Fund - Direct Growth", "nav": 82.15},
    {"scheme_name": "Parag Parikh Flexi Cap Fund - Regular Growth", "nav": 78.40},
    {"scheme_name": "SBI Bluechip Fund - Direct Growth", "nav": 95.70},
    {"scheme_name": "SBI Bluechip Fund - Regular Growth", "nav": 88.10},
    {"scheme_name": "HDFC Flexicap Fund - Direct Growth", "nav": 2145.30},
    {"scheme_name": "ICICI Prudential Bluechip Fund - Direct Growth", "nav": 105.85},
    {"scheme_name": "Axis Bluechip Fund - Direct Growth", "nav": 68.90},
    {"scheme_name": "Kotak Flexicap Fund - Direct Growth", "nav": 78.25},
    {"scheme_name": "Nippon India Small Cap Fund - Direct Growth", "nav": 210.40},
    {"scheme_name": "Quant Small Cap Fund - Direct Growth", "nav": 245.80},
]

headers = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}

def get_conn():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return pg8000.connect(RDS_USER, host=RDS_HOST, port=RDS_PORT, database=RDS_DB, password=RDS_PASS, ssl_context=ssl_context)

def normalize(name):
    name = name.lower()
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    # drop noise words that don't help matching
    noise = {"fund", "direct", "regular", "growth", "plan", "the"}
    tokens = [t for t in name.split() if t not in noise]
    return set(tokens)

def fuzzy_match(scheme_name, dataset):
    target_tokens = normalize(scheme_name)
    if not target_tokens:
        return None
    best = None
    best_score = 0
    for entry in dataset:
        entry_tokens = normalize(entry["scheme_name"])
        overlap = len(target_tokens & entry_tokens)
        union = len(target_tokens | entry_tokens)
        score = overlap / union if union else 0
        if score > best_score:
            best_score = score
            best = entry
    # require a reasonable overlap to avoid false matches
    if best and best_score >= 0.4:
        return best
    return None

def lambda_handler(event, context):
    try:
        conn = get_conn()
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute("SELECT investment_id, scheme_name, units_held FROM investments WHERE units_held IS NOT NULL AND units_held > 0")
        rows = cur.fetchall()

        updated = []
        skipped = []

        for investment_id, scheme_name, units_held in rows:
            match = fuzzy_match(scheme_name, NAV_DATASET)
            if not match:
                skipped.append(scheme_name)
                continue
            new_value = round(float(units_held) * match["nav"], 2)
            cur.execute(
                "UPDATE investments SET current_value = %s, last_updated = NOW() WHERE investment_id = %s",
                (new_value, investment_id)
            )
            updated.append({"scheme_name": scheme_name, "matched_to": match["scheme_name"], "nav": match["nav"], "new_current_value": new_value})

        conn.close()
        return {"statusCode": 200, "headers": headers, "body": json.dumps({
            "status": "done",
            "updated_count": len(updated),
            "skipped_count": len(skipped),
            "updated": updated,
            "skipped": skipped
        })}
    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}

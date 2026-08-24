import os
import json
import pg8000
import ssl
import datetime
import uuid

RDS_HOST = "wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com"
RDS_PORT = 5432
RDS_DB = "wealthguard"
RDS_USER = "wealthguard_admin"
RDS_PASS = "os.environ.get("RDS_PASSWORD")"

CATEGORY_RULES = {
    "grocery": ["bigbasket", "grofers", "dmart", "reliance fresh", "more supermarket"],
    "food": ["zomato", "swiggy", "dominos", "mcdonald", "kfc", "starbucks"],
    "transport": ["uber", "ola", "rapido", "irctc", "indigo", "petrol", "fuel"],
    "shopping": ["amazon", "flipkart", "myntra", "ajio", "nykaa"],
    "entertainment": ["netflix", "prime video", "hotstar", "spotify", "bookmyshow"],
    "utilities": ["electricity", "water bill", "broadband", "airtel", "jio", "vodafone"],
    "crypto": ["binance", "coindcx", "wazirx", "crypto"],
    "cash": ["atm withdrawal", "cash withdrawal"],
    "transfer": ["neft", "imps", "upi transfer", "rtgs"],
    "ppf": ["ppf deposit", "public provident fund"],
    "elss": ["elss", "mutual fund sip", "tax saver fund"],
    "nps": ["nps contribution", "national pension"],
    "medical_insurance": ["health insurance", "mediclaim"],
    "hra": ["rent payment", "house rent"]
}

def get_db_conn():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return pg8000.connect(
        RDS_USER,
        host=RDS_HOST,
        port=RDS_PORT,
        database=RDS_DB,
        password=RDS_PASS,
        ssl_context=ssl_context
    )

def categorize(merchant, provided_category=None):
    if provided_category:
        return provided_category.lower()
    merchant_lower = (merchant or "").lower()
    for category, keywords in CATEGORY_RULES.items():
        if any(kw in merchant_lower for kw in keywords):
            return category
    return "uncategorized"

def lambda_handler(event, context):
    body = event if isinstance(event, dict) else json.loads(event.get("body", "{}"))
    transaction = body.get("transaction", body)

    transaction_id = str(transaction.get("transaction_id", str(uuid.uuid4())))
    user_id = transaction.get("user_id")
    amount = float(transaction.get("amount", 0))
    merchant = transaction.get("merchant_name", transaction.get("merchant", "Unknown"))
    provided_category = transaction.get("category")
    tx_date = transaction.get("timestamp", datetime.datetime.utcnow().isoformat())
    status = transaction.get("status", "completed")

    category = categorize(merchant, provided_category)

    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO transactions (transaction_id, user_id, amount, category, merchant, transaction_date, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (transaction_id) DO UPDATE SET
                category = EXCLUDED.category,
                status = EXCLUDED.status
        """, (transaction_id, user_id, amount, category, merchant, tx_date, status))
        conn.commit()
        cur.close()

        result = {
            "transaction_id": transaction_id,
            "user_id": user_id,
            "amount": amount,
            "category": category,
            "merchant": merchant,
            "status": status,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        print(f"Transaction {transaction_id} categorized as {category} for user {user_id}")
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        print(f"Error processing transaction: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
    finally:
        conn.close()

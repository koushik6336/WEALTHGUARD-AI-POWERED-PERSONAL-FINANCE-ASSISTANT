import os
import json
import pg8000
import ssl
from datetime import datetime

RDS_HOST = "wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com"
RDS_USER = "wealthguard_admin"
RDS_PASS = "os.environ.get("RDS_PASSWORD")"
RDS_DB = "wealthguard"
RDS_PORT = 5432

headers = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*"
}

def get_conn():
    return pg8000.connect(
        RDS_USER, host=RDS_HOST, port=RDS_PORT,
        database=RDS_DB, password=RDS_PASS, ssl_context=True
    )

def lambda_handler(event, context):
    method = event.get("httpMethod", "GET")
    params = event.get("queryStringParameters") or {}

    try:
        conn = get_conn()
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS spend_entries (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                date DATE NOT NULL DEFAULT CURRENT_DATE,
                amount DECIMAL(18,2) NOT NULL,
                category VARCHAR DEFAULT 'other',
                note VARCHAR,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        if method == "POST":
            body = json.loads(event.get("body") or "{}")
            user_id = body.get("user_id")
            amount = body.get("amount")
            category = body.get("category", "other")
            note = body.get("note", "")
            date = body.get("date", str(datetime.now().date()))

            if not user_id or not amount:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "user_id and amount required"})}

            cur.execute(
                "INSERT INTO spend_entries (user_id, date, amount, category, note) VALUES (%s, %s, %s, %s, %s)",
                (user_id, date, float(amount), category, note)
            )
            return {"statusCode": 200, "headers": headers, "body": json.dumps({"status": "logged"})}

        elif method == "GET":
            user_id = params.get("user_id")
            if not user_id:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "user_id required"})}

            # Monthly summary by category
            cur.execute("""
                SELECT category, COALESCE(SUM(amount),0)
                FROM spend_entries
                WHERE user_id = %s AND DATE_TRUNC('month', date) = DATE_TRUNC('month', CURRENT_DATE)
                GROUP BY category ORDER BY SUM(amount) DESC
            """, (user_id,))
            by_category = [{"category": r[0], "spent": float(r[1])} for r in cur.fetchall()]

            # Total spent this month
            cur.execute("""
                SELECT COALESCE(SUM(amount),0) FROM spend_entries
                WHERE user_id = %s AND DATE_TRUNC('month', date) = DATE_TRUNC('month', CURRENT_DATE)
            """, (user_id,))
            total_spent = float(cur.fetchone()[0])

            # Entries grouped by date
            cur.execute("""
                SELECT date, json_agg(json_build_object(
                    'id', id, 'amount', amount, 'category', category, 'note', note
                ) ORDER BY created_at DESC)
                FROM spend_entries
                WHERE user_id = %s AND DATE_TRUNC('month', date) = DATE_TRUNC('month', CURRENT_DATE)
                GROUP BY date ORDER BY date DESC
            """, (user_id,))
            by_date = [{"date": str(r[0]), "entries": r[1]} for r in cur.fetchall()]

            # Check if yesterday has any entry
            cur.execute("""
                SELECT COUNT(*) FROM spend_entries
                WHERE user_id = %s AND date = CURRENT_DATE - INTERVAL '1 day'
            """, (user_id,))
            yesterday_logged = cur.fetchone()[0] > 0

            conn.close()
            return {"statusCode": 200, "headers": headers, "body": json.dumps({
                "total_spent": total_spent,
                "by_category": by_category,
                "by_date": by_date,
                "yesterday_logged": yesterday_logged
            })}

    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}

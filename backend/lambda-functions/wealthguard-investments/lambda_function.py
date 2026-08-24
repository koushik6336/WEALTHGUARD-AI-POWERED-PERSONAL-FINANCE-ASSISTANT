import os
import json
import pg8000

RDS_HOST = "wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com"
RDS_USER = "wealthguard_admin"
RDS_PASS = "os.environ.get("RDS_PASSWORD")"
RDS_DB = "wealthguard"
RDS_PORT = 5432

headers = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}

def get_conn():
    return pg8000.connect(RDS_USER, host=RDS_HOST, port=RDS_PORT, database=RDS_DB, password=RDS_PASS, ssl_context=True)

def lambda_handler(event, context):
    method = event.get("httpMethod", "GET")
    params = event.get("queryStringParameters") or {}

    try:
        conn = get_conn()
        conn.autocommit = True
        cur = conn.cursor()

        # Ensure investments table has needed columns
        cur.execute("""
            ALTER TABLE investments
            ADD COLUMN IF NOT EXISTS scheme_name VARCHAR,
            ADD COLUMN IF NOT EXISTS amfi_code VARCHAR,
            ADD COLUMN IF NOT EXISTS folio_number VARCHAR,
            ADD COLUMN IF NOT EXISTS units_held DECIMAL(18,4) DEFAULT 0,
            ADD COLUMN IF NOT EXISTS amount_invested DECIMAL(18,2) DEFAULT 0,
            ADD COLUMN IF NOT EXISTS current_value DECIMAL(18,2) DEFAULT 0,
            ADD COLUMN IF NOT EXISTS source VARCHAR DEFAULT 'manual',
            ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP DEFAULT NOW()
        """)

        if method == "POST":
            body = json.loads(event.get("body") or "{}")
            user_id = body.get("user_id")
            scheme_name = body.get("scheme_name")
            amount_invested = body.get("amount_invested", 0)
            current_value = body.get("current_value", 0)
            units_held = body.get("units_held", 0)

            if not user_id or not scheme_name:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "user_id and scheme_name required"})}

            cur.execute("""
                INSERT INTO investments (user_id, scheme_name, amount_invested, current_value, units_held, investment_type, source, last_updated)
                VALUES (%s, %s, %s, %s, %s, 'mutual_fund', 'manual', NOW())
            """, (user_id, scheme_name, float(amount_invested), float(current_value), float(units_held)))

            conn.close()
            return {"statusCode": 200, "headers": headers, "body": json.dumps({"status": "added"})}

        elif method == "GET":
            user_id = params.get("user_id")
            if not user_id:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "user_id required"})}

            cur.execute("""
                SELECT scheme_name, amount_invested, current_value, units_held, investment_type, last_updated
                FROM investments WHERE user_id=%s ORDER BY current_value DESC
            """, (user_id,))

            holdings = []
            total_invested = 0
            total_current = 0

            for r in cur.fetchall():
                invested = float(r[1]) if r[1] else 0
                current = float(r[2]) if r[2] else 0
                ret_pct = round(((current - invested) / invested * 100), 2) if invested > 0 else 0
                total_invested += invested
                total_current += current
                holdings.append({
                    "scheme_name": r[0],
                    "amount_invested": invested,
                    "current_value": current,
                    "return_pct": ret_pct,
                    "investment_type": r[4]
                })

            overall_return = round(((total_current - total_invested) / total_invested * 100), 2) if total_invested > 0 else 0

            conn.close()
            return {"statusCode": 200, "headers": headers, "body": json.dumps({
                "total_invested": total_invested,
                "total_current_value": total_current,
                "overall_return_pct": overall_return,
                "holdings": holdings
            })}

    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}

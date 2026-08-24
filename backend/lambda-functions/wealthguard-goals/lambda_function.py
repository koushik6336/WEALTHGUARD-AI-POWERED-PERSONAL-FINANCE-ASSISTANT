import os
import json
import pg8000
from datetime import datetime

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
        cur.execute("ALTER TABLE goals ADD COLUMN IF NOT EXISTS goal_type VARCHAR DEFAULT 'custom'")

        if method == "POST":
            body = json.loads(event.get("body") or "{}")
            user_id = body.get("user_id")
            goal_type = body.get("goal_type", "custom")
            goal_name = body.get("goal_name")
            target_amount = body.get("target_amount")
            target_date = body.get("target_date")
            current_amount = body.get("current_amount", 0)
            if not user_id or not goal_name or not target_amount:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "missing fields"})}
            cur.execute("INSERT INTO goals (user_id, goal_type, goal_name, target_amount, current_amount, target_date, status, created_at) VALUES (%s,%s,%s,%s,%s,%s,'active',NOW())",
                (user_id, goal_type, goal_name, float(target_amount), float(current_amount), target_date))
            conn.close()
            return {"statusCode": 200, "headers": headers, "body": json.dumps({"status": "created"})}

        elif method == "GET":
            user_id = params.get("user_id")
            if not user_id:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "user_id required"})}
            cur.execute("SELECT goal_name, goal_type, target_amount, current_amount, target_date, status FROM goals WHERE user_id=%s AND status='active' ORDER BY created_at ASC", (user_id,))
            goals = []
            for r in cur.fetchall():
                target = float(r[2])
                current = float(r[3]) if r[3] else 0
                pct = round((current / target * 100), 1) if target > 0 else 0
                goals.append({"goal_name": r[0], "goal_type": r[1], "target_amount": target, "current_amount": current, "target_date": str(r[4]) if r[4] else None, "progress_pct": pct})
            conn.close()
            return {"statusCode": 200, "headers": headers, "body": json.dumps({"goals": goals})}

        elif method == "PUT":
            body = json.loads(event.get("body") or "{}")
            cur.execute("UPDATE goals SET current_amount=%s WHERE user_id=%s AND goal_name=%s",
                (float(body.get("current_amount",0)), body.get("user_id"), body.get("goal_name")))
            conn.close()
            return {"statusCode": 200, "headers": headers, "body": json.dumps({"status": "updated"})}

    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}

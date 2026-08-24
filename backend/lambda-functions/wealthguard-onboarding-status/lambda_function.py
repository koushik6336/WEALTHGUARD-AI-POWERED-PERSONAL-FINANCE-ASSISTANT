import os
import json
import pg8000
import ssl

RDS_HOST = "wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com"
RDS_USER = "wealthguard_admin"
RDS_PASS = "os.environ.get("RDS_PASSWORD")"
RDS_DB = "wealthguard"
RDS_PORT = 5432

headers = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}

FLAG_COLUMNS = ["budget_onboarded", "goals_onboarded", "tax_onboarded", "investments_onboarded"]

def get_conn():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return pg8000.connect(RDS_USER, host=RDS_HOST, port=RDS_PORT, database=RDS_DB, password=RDS_PASS, ssl_context=ssl_context)

def lambda_handler(event, context):
    method = event.get("httpMethod", "GET")
    try:
        conn = get_conn()
        conn.autocommit = True
        cur = conn.cursor()

        if method == "GET":
            params = event.get("queryStringParameters") or {}
            user_id = params.get("user_id")
            if not user_id:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "user_id required"})}
            cur.execute(f"SELECT {', '.join(FLAG_COLUMNS)} FROM users WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
            conn.close()
            if not row:
                return {"statusCode": 404, "headers": headers, "body": json.dumps({"error": "user not found"})}
            result = {col: bool(val) for col, val in zip(FLAG_COLUMNS, row)}
            return {"statusCode": 200, "headers": headers, "body": json.dumps(result)}

        elif method == "POST":
            body = json.loads(event.get("body") or "{}")
            user_id = body.get("user_id")
            flag = body.get("flag")
            if not user_id or flag not in FLAG_COLUMNS:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "user_id and valid flag required"})}
            cur.execute(f"UPDATE users SET {flag} = TRUE WHERE user_id=%s", (user_id,))
            conn.close()
            return {"statusCode": 200, "headers": headers, "body": json.dumps({"status": "updated", "flag": flag})}

        else:
            return {"statusCode": 405, "headers": headers, "body": json.dumps({"error": "method not allowed"})}

    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}

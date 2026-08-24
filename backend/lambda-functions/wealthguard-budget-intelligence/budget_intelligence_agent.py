import os
import json
import boto3
import pg8000
import ssl
import datetime
from botocore.config import Config

boto_config = Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 1})

RDS_HOST = "wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com"
RDS_PORT = 5432
RDS_DB = "wealthguard"
RDS_USER = "wealthguard_admin"
RDS_PASS = "os.environ.get("RDS_PASSWORD")"

SNS_BUDGET_ARN = "arn:aws:sns:ap-south-1:703890345539:wealthguard-budget-alerts"
REGION = "ap-south-1"

sns = boto3.client("sns", region_name=REGION, config=boto_config)

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

def send_budget_alert(user_id, category, spent, limit):
    pct = round((spent / limit) * 100, 1) if limit > 0 else 0
    message = (
        f"Budget alert for user {user_id}: "
        f"{category} spending is Rs.{spent:,.0f} of Rs.{limit:,.0f} limit ({pct}% used)."
    )
    sns.publish(
        TopicArn=SNS_BUDGET_ARN,
        Subject=f"WealthGuard Budget Alert - {user_id} - {category}",
        Message=message
    )
    return message

def process_user(conn, user_id):
    cur = conn.cursor()

    cur.execute("SELECT category, monthly_limit FROM budgets WHERE user_id = %s", (user_id,))
    budgets = cur.fetchall()

    results = []
    for category, monthly_limit in budgets:
        monthly_limit = float(monthly_limit)
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE user_id = %s
              AND category = %s
              AND transaction_date >= DATE_TRUNC('month', CURRENT_DATE)
        """, (user_id, category))
        spent = float(cur.fetchone()[0])

        pct_used = round((spent / monthly_limit) * 100, 1) if monthly_limit > 0 else 0
        alert_sent = False

        if pct_used >= 80:
            send_budget_alert(user_id, category, spent, monthly_limit)
            alert_sent = True

        results.append({
            "category": category,
            "monthly_limit": monthly_limit,
            "spent": spent,
            "pct_used": pct_used,
            "alert_sent": alert_sent
        })

    cur.close()
    return results

def lambda_handler(event, context):
    try:
        conn = get_db_conn()
    except Exception as e:
        print(f"RDS connection failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": f"Database connection failed: {str(e)}"})}

    try:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users")
        users = [r[0] for r in cur.fetchall()]
        cur.close()

        all_results = {}
        for user_id in users:
            try:
                all_results[user_id] = process_user(conn, user_id)
            except Exception as e:
                print(f"Error processing user {user_id}: {e}")
                all_results[user_id] = {"error": str(e)}

        return {
            "statusCode": 200,
            "body": json.dumps({
                "processed_users": len(users),
                "results": all_results,
                "timestamp": datetime.datetime.utcnow().isoformat()
            })
        }
    except Exception as e:
        print(f"Unhandled error in budget-intelligence: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
    finally:
        conn.close()

import os
import json
import boto3
import pg8000
import ssl
import datetime
from botocore.config import Config

boto_config = Config(connect_timeout=3, read_timeout=8, retries={"max_attempts": 1})

REGION = "ap-south-1"
RDS_HOST = "wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com"
RDS_PORT = 5432
RDS_DB = "wealthguard"
RDS_USER = "wealthguard_admin"
RDS_PASS = "os.environ.get("RDS_PASSWORD")"

FRAUD_TABLE = "wealthguard-fraud-incidents"

dynamo = boto3.client("dynamodb", region_name=REGION, config=boto_config)


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


def get_recent_fraud_alerts():
    try:
        resp = dynamo.scan(TableName=FRAUD_TABLE, Limit=50)
        items = resp.get("Items", [])
        alerts = []
        for item in items:
            alerts.append({
                "transaction_id": item.get("transaction_id", {}).get("S", ""),
                "user_id": item.get("user_id", {}).get("S", ""),
                "fraud_score": float(item.get("fraud_score", {}).get("N", "0")),
                "risk_level": item.get("risk_level", {}).get("S", ""),
                "reasoning": item.get("reasoning", {}).get("S", ""),
                "detection_method": item.get("detection_method", {}).get("S", ""),
                "timestamp": item.get("incident_timestamp", {}).get("S", "")
            })
        alerts.sort(key=lambda x: x["timestamp"], reverse=True)
        return alerts[:10]
    except Exception as e:
        print(f"Fraud alerts fetch failed: {e}")
        return []


def get_budget_status(conn):
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT b.user_id, b.category, b.monthly_limit,
                   COALESCE(SUM(t.amount), 0) as spent
            FROM budgets b
            LEFT JOIN transactions t ON t.user_id = b.user_id
                AND t.category = b.category
                AND t.transaction_date >= DATE_TRUNC('month', CURRENT_DATE)
            GROUP BY b.user_id, b.category, b.monthly_limit
            ORDER BY b.user_id, b.category
        """)
        rows = cur.fetchall()
        cur.close()
        budgets = []
        for user_id, category, limit, spent in rows:
            limit = float(limit)
            spent = float(spent)
            pct = round((spent / limit) * 100, 1) if limit > 0 else 0
            budgets.append({
                "user_id": user_id,
                "category": category,
                "monthly_limit": limit,
                "spent": spent,
                "pct_used": pct
            })
        return budgets
    except Exception as e:
        print(f"Budget status fetch failed: {e}")
        return []


def get_goals_status(conn):
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, goal_name, target_amount, current_amount, target_date
            FROM goals
            WHERE status = 'active'
            ORDER BY user_id
        """)
        rows = cur.fetchall()
        cur.close()
        goals = []
        for user_id, goal_name, target, current, target_date in rows:
            target = float(target)
            current = float(current)
            pct = round((current / target) * 100, 1) if target > 0 else 0
            goals.append({
                "user_id": user_id,
                "goal_name": goal_name,
                "target_amount": target,
                "current_amount": current,
                "progress_pct": pct,
                "target_date": str(target_date)
            })
        return goals
    except Exception as e:
        print(f"Goals status fetch failed: {e}")
        return []


def get_tax_status(conn):
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, COALESCE(SUM(deductions), 0) as saved_80c
            FROM tax_records
            GROUP BY user_id
            ORDER BY user_id
        """)
        rows = cur.fetchall()
        cur.close()
        SECTION_80C_LIMIT = 150000.0
        tax_data = []
        for user_id, saved in rows:
            saved = float(saved) if saved else 0.0
            remaining = max(0, SECTION_80C_LIMIT - saved)
            tax_data.append({
                "user_id": user_id,
                "saved_80c": saved,
                "remaining_80c": remaining,
                "limit_80c": SECTION_80C_LIMIT
            })
        return tax_data
    except Exception as e:
        print(f"Tax status fetch failed: {e}")
        return []


def lambda_handler(event, context):
    try:
        conn = get_db_conn()
    except Exception as e:
        print(f"RDS connection failed: {e}")
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({
                "error": f"Database unavailable: {str(e)}",
                "fraud_alerts": get_recent_fraud_alerts(),
                "budgets": [],
                "goals": [],
                "tax": [],
                "timestamp": datetime.datetime.utcnow().isoformat()
            })
        }

    try:
        data = {
            "fraud_alerts": get_recent_fraud_alerts(),
            "budgets": get_budget_status(conn),
            "goals": get_goals_status(conn),
            "tax": get_tax_status(conn),
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps(data)
        }
    except Exception as e:
        print(f"Unhandled error in dashboard-data: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)})
        }
    finally:
        conn.close()

import os
import json
import boto3
import pg8000
import ssl
import datetime
import calendar
import time
from botocore.config import Config

boto_config = Config(connect_timeout=3, read_timeout=15, retries={"max_attempts": 1})

REGION = "ap-south-1"
BEDROCK_MODEL = "apac.amazon.nova-lite-v1:0"
RDS_HOST = "wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com"
RDS_PORT = 5432
RDS_DB = "wealthguard"
RDS_USER = "wealthguard_admin"
RDS_PASS = "os.environ.get("RDS_PASSWORD")"
FRAUD_TABLE = "wealthguard-fraud-incidents"

bedrock = boto3.client("bedrock-runtime", region_name=REGION, config=boto_config)
dynamo = boto3.client("dynamodb", region_name=REGION, config=boto_config)


def get_db_conn():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return pg8000.connect(
        RDS_USER, host=RDS_HOST, port=RDS_PORT, database=RDS_DB,
        password=RDS_PASS, ssl_context=ssl_context
    )


def user_exists(conn, user_id):
    cur = conn.cursor()
    cur.execute("SELECT user_id, name, salary FROM users WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    return row


def create_test_user(conn, user_id):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, name, email, salary, city, risk_profile, risk_appetite, monthly_budget)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO NOTHING
    """, (user_id, "Test User", f"{user_id}@wealthguard.local", 60000, "Unknown", "moderate", "medium", 40000))
    conn.commit()
    cur.close()


def get_budget_details(conn, user_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT b.category, b.monthly_limit, COALESCE(SUM(t.amount),0)
        FROM budgets b
        LEFT JOIN transactions t ON t.user_id = b.user_id AND t.category = b.category
            AND t.transaction_date >= DATE_TRUNC('month', CURRENT_DATE)
        WHERE b.user_id = %s
        GROUP BY b.category, b.monthly_limit
        ORDER BY (COALESCE(SUM(t.amount),0) / NULLIF(b.monthly_limit,0)) DESC
    """, (user_id,))
    rows = cur.fetchall()
    cur.close()

    categories = []
    total_limit = 0.0
    total_spent = 0.0
    worst_category = None
    worst_pct = 0

    for cat, limit, spent in rows:
        limit = float(limit)
        spent = float(spent)
        pct = round((spent / limit) * 100) if limit > 0 else 0
        categories.append({"category": cat, "limit": limit, "spent": spent, "pct_used": pct})
        total_limit += limit
        total_spent += spent
        if pct > worst_pct:
            worst_pct = pct
            worst_category = cat

    overall_pct = round((total_spent / total_limit) * 100) if total_limit > 0 else 0

    today = datetime.date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_left = days_in_month - today.day

    return {
        "categories": categories,
        "total_limit": total_limit,
        "total_spent": total_spent,
        "overall_pct": overall_pct,
        "days_left_in_month": days_left,
        "worst_category": worst_category,
        "worst_category_pct": worst_pct,
        "over_budget_amount": max(0, total_spent - total_limit)
    }


def get_investment_portfolio(conn, user_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT investment_type, COALESCE(SUM(amount),0), COALESCE(SUM(current_value),0)
        FROM investments WHERE user_id = %s GROUP BY investment_type
    """, (user_id,))
    rows = cur.fetchall()
    cur.close()

    by_type = []
    total_invested = 0.0
    total_current = 0.0
    for inv_type, invested, current in rows:
        invested = float(invested)
        current = float(current) if current else invested
        gain_pct = round(((current - invested) / invested) * 100, 1) if invested > 0 else 0
        by_type.append({"type": inv_type, "invested": invested, "current_value": current, "gain_pct": gain_pct})
        total_invested += invested
        total_current += current

    allocation = []
    if total_current > 0:
        for item in by_type:
            allocation.append({"type": item["type"], "pct_of_portfolio": round((item["current_value"] / total_current) * 100, 1)})

    return {
        "by_type": by_type,
        "total_invested": total_invested,
        "total_current_value": total_current,
        "total_gain_pct": round(((total_current - total_invested) / total_invested) * 100, 1) if total_invested > 0 else 0,
        "allocation": allocation
    }


def get_goals_with_pace(conn, user_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT goal_name, target_amount, current_amount, target_date
        FROM goals WHERE user_id = %s AND status = 'active' ORDER BY created_at ASC
    """, (user_id,))
    rows = cur.fetchall()
    cur.close()

    today = datetime.date.today()
    goals = []
    for name, target, current, target_date in rows:
        target = float(target)
        current = float(current)
        pct = round((current / target) * 100) if target > 0 else 0

        months_total = max(1, (target_date.year - today.year) * 12 + (target_date.month - today.month))
        required_monthly = (target - current) / months_total if months_total > 0 else 0

        goals.append({
            "goal_name": name, "target_amount": target, "current_amount": current,
            "progress_pct": pct, "target_date": str(target_date),
            "required_monthly_saving": round(required_monthly, 2)
        })
    return goals


def get_recent_transactions(conn, user_id, limit=8):
    cur = conn.cursor()
    cur.execute("""
        SELECT merchant, category, amount, transaction_date FROM transactions
        WHERE user_id = %s ORDER BY transaction_date DESC LIMIT %s
    """, (user_id, limit))
    rows = cur.fetchall()
    cur.close()
    return [{"merchant": r[0], "category": r[1], "amount": float(r[2]), "date": str(r[3])} for r in rows]


def get_tax_summary(conn, user_id):
    cur = conn.cursor()
    cur.execute("SELECT salary FROM users WHERE user_id = %s", (user_id,))
    salary_row = cur.fetchone()
    cur.execute("SELECT COALESCE(SUM(deductions),0) FROM tax_records WHERE user_id = %s", (user_id,))
    tax_row = cur.fetchone()
    cur.close()
    invested_80c = float(tax_row[0]) if tax_row and tax_row[0] else 0.0
    return {
        "annual_salary": (float(salary_row[0]) * 12) if salary_row and salary_row[0] else 0,
        "invested_80c": invested_80c,
        "remaining_80c": max(0, 150000 - invested_80c)
    }


def get_fraud_summary(user_id):
    try:
        resp = dynamo.scan(
            TableName=FRAUD_TABLE,
            FilterExpression="user_id = :uid",
            ExpressionAttributeValues={":uid": {"S": user_id}}
        )
        items = resp.get("Items", [])
        high_risk = [i for i in items if i.get("risk_level", {}).get("S", "") in ("HIGH", "CRITICAL")]
        return {"clear": len(high_risk) == 0, "alert_count": len(high_risk), "total_checked": len(items)}
    except Exception:
        return {"clear": True, "alert_count": 0, "total_checked": 0}


def compute_health_score(budget, investment, goals, fraud, tax):
    score = 100

    if budget["overall_pct"] > 100:
        score -= min(30, (budget["overall_pct"] - 100) * 0.5)
    elif budget["overall_pct"] > 80:
        score -= (budget["overall_pct"] - 80) * 0.5

    if goals:
        avg_progress = sum(g["progress_pct"] for g in goals) / len(goals)
        if avg_progress < 30:
            score -= 15
        elif avg_progress < 50:
            score -= 8

    if fraud["alert_count"] > 0:
        score -= min(20, fraud["alert_count"] * 10)

    if investment["total_gain_pct"] < 0:
        score -= 10

    if tax["remaining_80c"] > 100000:
        score -= 5

    return max(0, min(100, round(score)))


def call_bedrock(prompt, max_tokens=300):
    t0 = time.time()
    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL,
            body=json.dumps({
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": max_tokens}
            })
        )
        result = json.loads(response["body"].read())
        print(f"TIMING bedrock_call took {time.time()-t0:.2f}s")
        return result["output"]["message"]["content"][0]["text"]
    except Exception as e:
        print(f"TIMING bedrock_call FAILED after {time.time()-t0:.2f}s: {e}")
        return None


def generate_summary_and_alert(name, budget, goals, fraud, score):
    prompt = f"""You are WealthGuard. Based on this user's data, write TWO things:
1. A one-sentence warm greeting summary (under 22 words)
2. If overall budget usage is over 100 percent, a one-sentence alert about the overspend with the exact amount, otherwise say "none"

Name: {name}
Budget: {json.dumps(budget)}
Goals: {json.dumps(goals)}
Fraud alerts: {fraud['alert_count']}
Health score: {score}

Respond in this exact format:
SUMMARY: <sentence>
ALERT: <sentence or none>"""

    result = call_bedrock(prompt, max_tokens=150)
    summary_line = "Here is a quick look at your finances today."
    alert_line = None
    if result:
        for line in result.split("\n"):
            if line.strip().startswith("SUMMARY:"):
                summary_line = line.split("SUMMARY:", 1)[1].strip()
            elif line.strip().startswith("ALERT:"):
                a = line.split("ALERT:", 1)[1].strip()
                if a.lower() != "none":
                    alert_line = a
    return summary_line, alert_line


def lambda_handler(event, context_obj):
    t_start = time.time()
    if isinstance(event, dict) and "body" in event and "httpMethod" in event:
        params = event.get("queryStringParameters") or {}
        body = json.loads(event.get("body") or "{}") if event.get("body") else {}
        user_id = params.get("user_id") or body.get("user_id", "")
    else:
        body = event if isinstance(event, dict) else json.loads(event)
        user_id = body.get("user_id", "")

    headers = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
    user_id = (user_id or "").strip()

    if not user_id:
        return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "user_id is required"})}

    t0 = time.time()
    try:
        conn = get_db_conn()
    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": f"Database unavailable: {str(e)}"})}
    print(f"TIMING db_connect took {time.time()-t0:.2f}s")

    try:
        t0 = time.time()
        existing = user_exists(conn, user_id)
        is_new = existing is None
        if is_new:
            create_test_user(conn, user_id)
            name = "Test User"
        else:
            name = existing[1] or "Test User"
        print(f"TIMING user_exists/create took {time.time()-t0:.2f}s")

        t0 = time.time()
        budget = get_budget_details(conn, user_id)
        print(f"TIMING get_budget_details took {time.time()-t0:.2f}s")

        t0 = time.time()
        investment = get_investment_portfolio(conn, user_id)
        print(f"TIMING get_investment_portfolio took {time.time()-t0:.2f}s")

        t0 = time.time()
        goals = get_goals_with_pace(conn, user_id)
        print(f"TIMING get_goals_with_pace took {time.time()-t0:.2f}s")

        t0 = time.time()
        transactions = get_recent_transactions(conn, user_id)
        print(f"TIMING get_recent_transactions took {time.time()-t0:.2f}s")

        t0 = time.time()
        tax = get_tax_summary(conn, user_id)
        print(f"TIMING get_tax_summary took {time.time()-t0:.2f}s")

        t0 = time.time()
        fraud = get_fraud_summary(user_id)
        print(f"TIMING get_fraud_summary took {time.time()-t0:.2f}s")

        score = compute_health_score(budget, investment, goals, fraud, tax)

        t0 = time.time()
        summary_line, alert_line = generate_summary_and_alert(name, budget, goals, fraud, score)
        print(f"TIMING generate_summary_and_alert took {time.time()-t0:.2f}s")

        print(f"TIMING TOTAL handler took {time.time()-t_start:.2f}s")

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "user_id": user_id, "name": name, "is_new": is_new,
                "health_score": score,
                "summary_line": summary_line,
                "alert_line": alert_line,
                "budget": budget,
                "investment": investment,
                "goals": goals,
                "transactions": transactions,
                "tax": tax,
                "fraud": fraud,
                "timestamp": datetime.datetime.utcnow().isoformat()
            })
        }
    except Exception as e:
        print(f"Unhandled error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}
    finally:
        conn.close()

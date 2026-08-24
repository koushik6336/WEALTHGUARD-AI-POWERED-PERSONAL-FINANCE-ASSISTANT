import os
import json
import boto3
import pg8000
import ssl
import datetime
from botocore.config import Config

boto_config = Config(connect_timeout=3, read_timeout=8, retries={"max_attempts": 1})

REGION = "ap-south-1"
BEDROCK_MODEL = "apac.amazon.nova-lite-v1:0"
REPORTS_BUCKET = "wealthguard-reports-703890345539"
SNS_FRAUD_ARN = "arn:aws:sns:ap-south-1:703890345539:wealthguard-fraud-alerts"

RDS_HOST = "wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com"
RDS_PORT = 5432
RDS_DB = "wealthguard"
RDS_USER = "wealthguard_admin"
RDS_PASS = "os.environ.get("RDS_PASSWORD")"

FRAUD_TABLE = "wealthguard-fraud-incidents"
REPORTS_TABLE = "wealthguard-monthly-reports"

dynamo = boto3.client("dynamodb", region_name=REGION, config=boto_config)
bedrock = boto3.client("bedrock-runtime", region_name=REGION, config=boto_config)
s3 = boto3.client("s3", region_name=REGION, config=boto_config)
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


def get_fraud_incidents(user_id):
    try:
        resp = dynamo.scan(
            TableName=FRAUD_TABLE,
            FilterExpression="user_id = :uid",
            ExpressionAttributeValues={":uid": {"S": user_id}}
        )
        return resp.get("Items", [])
    except Exception as e:
        print(f"Fraud incidents scan failed for {user_id}: {e}")
        return []


def get_spending_by_category(conn, user_id):
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT category, COALESCE(SUM(amount), 0), COUNT(*)
            FROM transactions
            WHERE user_id = %s
              AND transaction_date >= DATE_TRUNC('month', CURRENT_DATE)
            GROUP BY category
            ORDER BY SUM(amount) DESC
        """, (user_id,))
        rows = cur.fetchall()
        cur.close()
        return [{"category": r[0], "total": float(r[1]), "count": r[2]} for r in rows]
    except Exception as e:
        print(f"Spending query failed for {user_id}: {e}")
        return []


def get_goals_progress(conn, user_id):
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT goal_name, target_amount, current_amount, target_date
            FROM goals
            WHERE user_id = %s AND status = 'active'
        """, (user_id,))
        rows = cur.fetchall()
        cur.close()
        goals = []
        for goal_name, target, current, target_date in rows:
            target = float(target)
            current = float(current)
            pct = round((current / target) * 100, 1) if target > 0 else 0
            goals.append({
                "goal_name": goal_name,
                "target_amount": target,
                "current_amount": current,
                "progress_pct": pct,
                "target_date": str(target_date)
            })
        return goals
    except Exception as e:
        print(f"Goals query failed for {user_id}: {e}")
        return []


def get_tax_summary(conn, user_id):
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(SUM(deductions), 0), COALESCE(SUM(gross_income), 0)
            FROM tax_records
            WHERE user_id = %s
        """, (user_id,))
        row = cur.fetchone()
        cur.close()
        return {
            "total_80c_saved": float(row[0]) if row[0] else 0.0,
            "gross_income": float(row[1]) if row[1] else 0.0
        }
    except Exception as e:
        print(f"Tax query failed for {user_id}: {e}")
        return {"total_80c_saved": 0.0, "gross_income": 0.0}


def get_investment_summary(conn, user_id):
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT investment_type, COALESCE(SUM(amount), 0), COALESCE(SUM(current_value), 0)
            FROM investments
            WHERE user_id = %s
            GROUP BY investment_type
        """, (user_id,))
        rows = cur.fetchall()
        cur.close()
        investments = []
        total_invested = 0.0
        total_current = 0.0
        for inv_type, invested, current_val in rows:
            invested = float(invested)
            current_val = float(current_val) if current_val else invested
            investments.append({
                "type": inv_type,
                "invested": invested,
                "current_value": current_val,
                "gain_loss": round(current_val - invested, 2)
            })
            total_invested += invested
            total_current += current_val
        return investments, total_invested, total_current
    except Exception as e:
        print(f"Investments query failed for {user_id}: {e}")
        return [], 0.0, 0.0


def get_salary(conn, user_id):
    try:
        cur = conn.cursor()
        cur.execute("SELECT salary FROM users WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        cur.close()
        return float(row[0]) if row and row[0] else 0.0
    except Exception as e:
        print(f"Salary query failed for {user_id}: {e}")
        return 0.0


def call_bedrock(prompt):
    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL,
            body=json.dumps({
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": 500}
            })
        )
        result = json.loads(response["body"].read())
        return result["output"]["message"]["content"][0]["text"]
    except Exception as e:
        print(f"Bedrock call failed: {e}")
        return f"Bedrock unavailable: {str(e)}"


def generate_report(conn, user_id):
    fraud_incidents = get_fraud_incidents(user_id)
    spending = get_spending_by_category(conn, user_id)
    goals = get_goals_progress(conn, user_id)
    tax_summary = get_tax_summary(conn, user_id)
    investments, total_invested, total_current = get_investment_summary(conn, user_id)
    salary = get_salary(conn, user_id)

    total_spent = sum(s["total"] for s in spending)
    net_worth_estimate = total_current + (salary - total_spent)

    fraud_summary = []
    for item in fraud_incidents[:5]:
        fraud_summary.append({
            "fraud_score": item.get("fraud_score", {}).get("N", "0"),
            "risk_level": item.get("risk_level", {}).get("S", "unknown")
        })

    structured_data = {
        "user_id": user_id,
        "salary": salary,
        "total_spent_this_month": round(total_spent, 2),
        "spending_by_category": spending,
        "net_worth_estimate": round(net_worth_estimate, 2),
        "investments": investments,
        "total_invested": round(total_invested, 2),
        "total_current_value": round(total_current, 2),
        "total_80c_saved": tax_summary["total_80c_saved"],
        "goals": goals,
        "fraud_incidents_count": len(fraud_incidents)
    }

    prompt = f"""You are a financial report generator for an Indian personal finance app.

User: {user_id}
Salary: Rs.{salary:,.0f}
Total spent this month: Rs.{total_spent:,.0f}
Spending by category: {json.dumps(spending)}
Net worth estimate: Rs.{net_worth_estimate:,.0f}
Investments: {json.dumps(investments)}
Total 80C saved this year: Rs.{tax_summary['total_80c_saved']:,.0f}
Goals progress: {json.dumps(goals)}
Fraud incidents this period: {len(fraud_incidents)}

Generate a monthly financial report with these sections:
1. Net worth change summary
2. Spending breakdown highlights
3. Investment performance summary
4. Tax savings summary (80C)
5. Goal progress summary
6. Exactly 3 action items with specific rupee amounts

Keep the entire report under 350 words. Use Indian Rupee (Rs.) formatting."""

    report_text = call_bedrock(prompt)

    report_content = f"""WealthGuard Monthly Report
User: {user_id}
Generated: {datetime.datetime.utcnow().isoformat()}

{report_text}
"""

    return report_content, structured_data


def lambda_handler(event, context):
    users = event.get("users", ["u001", "u002", "u003", "u004", "u005"]) if isinstance(event, dict) else ["u001", "u002", "u003", "u004", "u005"]

    today = datetime.date.today()
    month_str = today.strftime("%Y-%m")

    try:
        conn = get_db_conn()
    except Exception as e:
        print(f"RDS connection failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": f"Database connection failed: {str(e)}"})}

    results = []
    try:
        for user_id in users:
            try:
                report_content, structured_data = generate_report(conn, user_id)

                s3_key = f"reports/{month_str}/{user_id}.txt"
                s3.put_object(
                    Bucket=REPORTS_BUCKET,
                    Key=s3_key,
                    Body=report_content.encode("utf-8"),
                    ContentType="text/plain"
                )
                s3_link = f"s3://{REPORTS_BUCKET}/{s3_key}"

                dynamo.put_item(
                    TableName=REPORTS_TABLE,
                    Item={
                        "user_id": {"S": user_id},
                        "report_month": {"S": month_str},
                        "s3_key": {"S": s3_key},
                        "structured_data": {"S": json.dumps(structured_data)},
                        "generated_at": {"S": datetime.datetime.utcnow().isoformat()}
                    }
                )

                sns.publish(
                    TopicArn=SNS_FRAUD_ARN,
                    Subject=f"WealthGuard Monthly Report Ready - {user_id}",
                    Message=f"Your monthly report for {month_str} is ready. Location: {s3_link}"
                )

                results.append({
                    "user_id": user_id,
                    "s3_key": s3_key,
                    "net_worth_estimate": structured_data["net_worth_estimate"],
                    "status": "generated"
                })
                print(f"Report generated for {user_id} at {s3_key}")
            except Exception as e:
                print(f"Error generating report for {user_id}: {e}")
                results.append({"user_id": user_id, "status": "error", "error": str(e)})
    finally:
        conn.close()

    return {
        "statusCode": 200,
        "body": json.dumps({
            "month": month_str,
            "processed": len(results),
            "results": results,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
    }

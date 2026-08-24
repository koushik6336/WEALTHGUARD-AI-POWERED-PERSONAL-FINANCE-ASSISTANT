import os
import json
import boto3
import pg8000
import ssl
import datetime
from botocore.config import Config

boto_config = Config(connect_timeout=3, read_timeout=15, retries={"max_attempts": 1})

REGION = "ap-south-1"
BEDROCK_MODEL = "apac.amazon.nova-lite-v1:0"
RDS_HOST = "wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com"
RDS_PORT = 5432
RDS_DB = "wealthguard"
RDS_USER = "wealthguard_admin"
RDS_PASS = "os.environ.get("RDS_PASSWORD")"

bedrock = boto3.client("bedrock-runtime", region_name=REGION, config=boto_config)


def get_db_conn():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return pg8000.connect(
        RDS_USER, host=RDS_HOST, port=RDS_PORT, database=RDS_DB,
        password=RDS_PASS, ssl_context=ssl_context
    )


def call_bedrock(prompt, max_tokens=300):
    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL,
            body=json.dumps({
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": max_tokens}
            })
        )
        result = json.loads(response["body"].read())
        return result["output"]["message"]["content"][0]["text"]
    except Exception as e:
        print(f"Bedrock call failed: {e}")
        return None


def generate_insight(name, salary, rent_emi, expenses, goal_name, goal_amount, risk_appetite, disposable):
    prompt = f"""You are WealthGuard, a friendly personal financial advisor AI for an Indian user.

A new user just shared their financial profile:
Name: {name}
Monthly salary: Rs.{salary:,.0f}
Monthly rent/EMI: Rs.{rent_emi:,.0f}
Monthly other expenses: Rs.{expenses:,.0f}
Disposable income: Rs.{disposable:,.0f}
Goal: {goal_name} (Rs.{goal_amount:,.0f})
Risk appetite: {risk_appetite}

Write ONE encouraging, specific paragraph (under 100 words) giving them an initial insight
about their financial position and how feasible their goal is given their disposable income.
Use their real numbers in rupees."""
    result = call_bedrock(prompt, max_tokens=200)
    return result or "Thanks for sharing your details. Based on your income and expenses, we will help you track your budget and reach your goals."


def lambda_handler(event, context_obj):
    if isinstance(event, dict) and "body" in event and "httpMethod" in event:
        body = json.loads(event.get("body") or "{}")
    else:
        body = event if isinstance(event, dict) else json.loads(event)

    headers = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}

    action = (body.get("action") or "").strip().lower()
    user_id = (body.get("user_id") or "").strip()
    name = (body.get("name") or "New User").strip()

    try:
        salary = float(body.get("salary") or 0)
        rent_emi = float(body.get("rent_emi") or 0)
        expenses = float(body.get("expenses") or 0)
        goal_amount = float(body.get("goal_amount") or 0)
    except (TypeError, ValueError):
        return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "salary, rent_emi, expenses, goal_amount must be numeric"})}

    goal_name = (body.get("goal_name") or "Savings Goal").strip()
    risk_appetite = (body.get("risk_appetite") or "medium").strip().lower()

    if action not in ("preview", "confirm"):
        return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "action must be 'preview' or 'confirm'"})}

    if action == "confirm" and not user_id:
        return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "user_id is required for confirm"})}

    disposable_income = salary - rent_emi - expenses

    parsed = {
        "name": name,
        "salary": salary,
        "rent_emi": rent_emi,
        "expenses": expenses,
        "goal_name": goal_name,
        "goal_amount": goal_amount,
        "risk_appetite": risk_appetite
    }

    if action == "preview":
        summary = generate_insight(name, salary, rent_emi, expenses, goal_name, goal_amount, risk_appetite, disposable_income)
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "summary": summary,
                "disposable_income": disposable_income,
                "parsed": parsed
            })
        }

    # action == confirm
    try:
        conn = get_db_conn()
    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": f"Database unavailable: {str(e)}"})}

    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (user_id, name, email, salary, city, risk_profile, risk_appetite, monthly_budget)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                name = EXCLUDED.name,
                salary = EXCLUDED.salary,
                risk_appetite = EXCLUDED.risk_appetite,
                monthly_budget = EXCLUDED.monthly_budget
        """, (user_id, name, f"{user_id}@wealthguard.local", salary, "Unknown",
              risk_appetite, risk_appetite, disposable_income))

        if goal_name and goal_amount > 0:
            cur.execute("""
                INSERT INTO goals (user_id, goal_name, target_amount, current_amount, target_date, status)
                VALUES (%s, %s, %s, 0, CURRENT_DATE + INTERVAL '2 years', 'active')
            """, (user_id, goal_name, goal_amount))

        if rent_emi > 0:
            cur.execute("""
                INSERT INTO budgets (user_id, category, monthly_limit)
                VALUES (%s, 'rent_emi', %s)
                ON CONFLICT DO NOTHING
            """, (user_id, rent_emi))

        conn.commit()
        cur.close()

        return {"statusCode": 200, "headers": headers, "body": json.dumps({"status": "saved"})}

    except Exception as e:
        print(f"Unhandled error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}
    finally:
        conn.close()

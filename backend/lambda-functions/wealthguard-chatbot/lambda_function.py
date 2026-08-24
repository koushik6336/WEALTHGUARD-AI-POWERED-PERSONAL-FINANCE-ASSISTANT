import os
import json
import boto3
import pg8000
import ssl
import datetime
import re
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
    cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    return row is not None


def extract_number(text):
    cleaned = re.sub(r"[,\u20b9]", "", text)
    match = re.search(r"(\d+(\.\d+)?)", cleaned)
    return float(match.group(1)) if match else None


def call_bedrock(prompt, max_tokens=400):
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


def classify_intent(message):
    prompt = f"""Classify this user message into EXACTLY ONE category:
budget, investment, tax, goals, fraud, profile_update, general

Use "profile_update" if the user is telling you new or changed information about
themselves (e.g. "my income went up to 90000", "I got a new loan of 5000 EMI",
"I want to add a new goal").

User message: "{message}"

Respond with ONLY the single category word."""
    result = call_bedrock(prompt, max_tokens=20)
    if not result:
        return "general"
    result = result.strip().lower()
    for v in ["profile_update", "budget", "investment", "tax", "goals", "fraud", "general"]:
        if v in result:
            return v
    return "general"


def detect_profile_update(conn, user_id, message):
    prompt = f"""The user said: "{message}"

Does this contain an update to their financial profile (new income amount, new EMI/loan
amount, or a new financial goal with a target amount)? Extract ONLY what is explicitly stated.

Respond with ONLY a JSON object in this exact format, no other text:
{{"income": <number or null>, "emi": <number or null>, "goal_name": <string or null>, "goal_amount": <number or null>}}

If nothing is mentioned for a field, use null."""

    result = call_bedrock(prompt, max_tokens=150)
    if not result:
        return None
    try:
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        return json.loads(cleaned.strip())
    except Exception as e:
        print(f"Profile update parse failed: {e}")
        return None


def apply_profile_update(conn, user_id, updates):
    cur = conn.cursor()
    changes = []

    if updates.get("income") is not None:
        cur.execute("UPDATE users SET salary = %s WHERE user_id = %s", (updates["income"], user_id))
        changes.append(f"income updated to Rs.{updates['income']:,.0f}")

    if updates.get("emi") is not None:
        cur.execute("""
            INSERT INTO budgets (user_id, category, monthly_limit)
            VALUES (%s, 'emi_liabilities', %s)
            ON CONFLICT DO NOTHING
        """, (user_id, updates["emi"]))
        cur.execute("""
            UPDATE budgets SET monthly_limit = %s WHERE user_id = %s AND category = 'emi_liabilities'
        """, (updates["emi"], user_id))
        changes.append(f"EMI updated to Rs.{updates['emi']:,.0f}")

    if updates.get("goal_name") and updates.get("goal_amount"):
        cur.execute("""
            INSERT INTO goals (user_id, goal_name, target_amount, current_amount, target_date, status)
            VALUES (%s, %s, %s, 0, CURRENT_DATE + INTERVAL '2 years', 'active')
        """, (user_id, updates["goal_name"], updates["goal_amount"]))
        changes.append(f"new goal added: {updates['goal_name']} (Rs.{updates['goal_amount']:,.0f})")

    conn.commit()
    cur.close()
    return changes


def create_new_user(conn, user_id, name, income, emi, goal_name, goal_amount):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, name, email, salary, city, risk_profile, risk_appetite, monthly_budget)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO NOTHING
    """, (user_id, name or "New User", f"{user_id}@wealthguard.local", income, "Unknown",
          "moderate", "medium", max(0, income - emi) if income and emi else income))
    if goal_name and goal_amount:
        cur.execute("""
            INSERT INTO goals (user_id, goal_name, target_amount, current_amount, target_date, status)
            VALUES (%s, %s, %s, 0, CURRENT_DATE + INTERVAL '2 years', 'active')
        """, (user_id, goal_name, goal_amount))
    if emi:
        cur.execute("""
            INSERT INTO budgets (user_id, category, monthly_limit)
            VALUES (%s, 'emi_liabilities', %s)
        """, (user_id, emi))
    conn.commit()
    cur.close()


def get_budget_data(conn, user_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT b.category, b.monthly_limit, COALESCE(SUM(t.amount),0)
        FROM budgets b
        LEFT JOIN transactions t ON t.user_id = b.user_id AND t.category = b.category
            AND t.transaction_date >= DATE_TRUNC('month', CURRENT_DATE)
        WHERE b.user_id = %s
        GROUP BY b.category, b.monthly_limit
    """, (user_id,))
    rows = cur.fetchall()
    cur.close()
    return [{"category": r[0], "limit": float(r[1]), "spent": float(r[2])} for r in rows]


def get_investment_data(conn, user_id):
    cur = conn.cursor()
    cur.execute("SELECT salary, risk_appetite FROM users WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    return {"salary": float(row[0]) if row else 0, "risk_appetite": row[1] if row else "medium"}


def get_tax_data(conn, user_id):
    cur = conn.cursor()
    cur.execute("SELECT salary FROM users WHERE user_id = %s", (user_id,))
    salary_row = cur.fetchone()
    cur.execute("SELECT COALESCE(SUM(deductions),0) FROM tax_records WHERE user_id = %s", (user_id,))
    tax_row = cur.fetchone()
    cur.close()
    return {
        "annual_salary": float(salary_row[0]) * 12 if salary_row and salary_row[0] else 0,
        "invested_80c": float(tax_row[0]) if tax_row and tax_row[0] else 0
    }


def get_goals_data(conn, user_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT goal_name, target_amount, current_amount, target_date
        FROM goals WHERE user_id = %s AND status = 'active'
    """, (user_id,))
    rows = cur.fetchall()
    cur.close()
    return [{"name": r[0], "target": float(r[1]), "current": float(r[2]), "date": str(r[3])} for r in rows]


def get_fraud_data(user_id):
    try:
        resp = dynamo.scan(
            TableName=FRAUD_TABLE,
            FilterExpression="user_id = :uid",
            ExpressionAttributeValues={":uid": {"S": user_id}}
        )
        items = resp.get("Items", [])
        return [{"score": i.get("fraud_score",{}).get("N","0"), "risk": i.get("risk_level",{}).get("S","")} for i in items[:5]]
    except Exception:
        return []


def generate_advice(intent, user_id, message, data):
    prompt = f"""You are WealthGuard, a friendly personal financial advisor AI for an Indian user.

The user asked: "{message}"
Category: {intent}
Their real data: {json.dumps(data, indent=2)}

Give a specific, actionable answer using their REAL numbers in Rs. Be direct and helpful,
like a smart advisor. If data shows a problem, point it out. Keep it under 180 words."""
    answer = call_bedrock(prompt, max_tokens=400)
    return answer or "I had trouble generating advice right now. Please try again."


def lambda_handler(event, context_obj):
    if isinstance(event, dict) and "body" in event and "httpMethod" in event:
        body = json.loads(event.get("body") or "{}")
    else:
        body = event if isinstance(event, dict) else json.loads(event)

    user_id = body.get("user_id", "").strip()
    message = body.get("message", "").strip()
    onboarding_stage = body.get("onboarding_stage", "")
    onboarding_data = body.get("onboarding_data", {})
    headers = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}

    if not user_id or not message:
        return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "user_id and message required"})}

    try:
        conn = get_db_conn()
    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": f"Database unavailable: {str(e)}"})}

    try:
        exists = user_exists(conn, user_id)

        if not exists:
            if onboarding_stage == "" or onboarding_stage == "start":
                return {"statusCode": 200, "headers": headers, "body": json.dumps({
                    "response": "Hey there! I am WealthGuard, your personal finance assistant. Good to have you here. I do not have your details yet, so let us set up your profile first, it only takes a minute. What is your approximate monthly income (in Rs.)?",
                    "intent": "onboarding", "onboarding_stage": "awaiting_income",
                    "onboarding_data": {},
                    "timestamp": datetime.datetime.utcnow().isoformat()
                })}

            elif onboarding_stage == "awaiting_income":
                income = extract_number(message)
                if income is None:
                    return {"statusCode": 200, "headers": headers, "body": json.dumps({
                        "response": "Sorry, I could not understand that as a number. What is your approximate monthly income in rupees? (e.g. 60000)",
                        "intent": "onboarding", "onboarding_stage": "awaiting_income",
                        "onboarding_data": onboarding_data,
                        "timestamp": datetime.datetime.utcnow().isoformat()
                    })}
                onboarding_data["income"] = income
                return {"statusCode": 200, "headers": headers, "body": json.dumps({
                    "response": f"Got it, Rs.{income:,.0f} per month. Do you have any loans or EMIs? If yes, what is the total monthly EMI amount? If none, just say 0.",
                    "intent": "onboarding", "onboarding_stage": "awaiting_emi",
                    "onboarding_data": onboarding_data,
                    "timestamp": datetime.datetime.utcnow().isoformat()
                })}

            elif onboarding_stage == "awaiting_emi":
                emi = extract_number(message) or 0
                onboarding_data["emi"] = emi
                return {"statusCode": 200, "headers": headers, "body": json.dumps({
                    "response": "Understood. What is one financial goal you are working towards? (e.g. Emergency Fund, Home Down Payment, Car Purchase) And roughly how much do you want to save for it?",
                    "intent": "onboarding", "onboarding_stage": "awaiting_goal",
                    "onboarding_data": onboarding_data,
                    "timestamp": datetime.datetime.utcnow().isoformat()
                })}

            elif onboarding_stage == "awaiting_goal":
                goal_amount = extract_number(message)
                goal_name = re.sub(r"[\d,.]+", "", message).strip(" .,-") or "Savings Goal"
                income = onboarding_data.get("income", 0)
                emi = onboarding_data.get("emi", 0)

                create_new_user(conn, user_id, None, income, emi, goal_name, goal_amount)

                summary = f"""Great, your profile is set up:
- Monthly income: Rs.{income:,.0f}
- Monthly EMI/liabilities: Rs.{emi:,.0f}
- Goal: {goal_name}{f' (Rs.{goal_amount:,.0f})' if goal_amount else ''}

I will remember this. You can now ask me about your budget, investment ideas, tax savings, or goal progress -- or just tell me if anything changes, like a new income or a new goal, and I will update your profile. What would you like to know?"""

                return {"statusCode": 200, "headers": headers, "body": json.dumps({
                    "response": summary,
                    "intent": "onboarding_complete", "onboarding_stage": "done",
                    "onboarding_data": onboarding_data,
                    "timestamp": datetime.datetime.utcnow().isoformat()
                })}

        intent = classify_intent(message)

        if intent == "profile_update":
            updates = detect_profile_update(conn, user_id, message)
            if updates:
                changes = apply_profile_update(conn, user_id, updates)
                if changes:
                    response_text = "Got it, I have updated your profile: " + "; ".join(changes) + ". Anything else you would like help with?"
                else:
                    response_text = "I noticed you mentioned a change, but could not pick out specific numbers. Could you tell me the exact amount?"
            else:
                response_text = "I noticed you mentioned a change, but could not pick out specific numbers. Could you tell me the exact amount?"

            return {"statusCode": 200, "headers": headers, "body": json.dumps({
                "response": response_text, "intent": "profile_update", "onboarding_stage": "done",
                "onboarding_data": onboarding_data,
                "timestamp": datetime.datetime.utcnow().isoformat()
            })}

        if intent == "budget":
            data = get_budget_data(conn, user_id)
        elif intent == "investment":
            data = get_investment_data(conn, user_id)
        elif intent == "tax":
            data = get_tax_data(conn, user_id)
        elif intent == "goals":
            data = get_goals_data(conn, user_id)
        elif intent == "fraud":
            data = get_fraud_data(user_id)
        else:
            data = {"budgets": get_budget_data(conn, user_id), "goals": get_goals_data(conn, user_id)}

        answer = generate_advice(intent, user_id, message, data)

        return {"statusCode": 200, "headers": headers, "body": json.dumps({
            "response": answer, "intent": intent, "onboarding_stage": "done",
            "onboarding_data": onboarding_data,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })}

    except Exception as e:
        print(f"Unhandled error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}
    finally:
        conn.close()

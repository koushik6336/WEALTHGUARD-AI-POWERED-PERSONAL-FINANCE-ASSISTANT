import json
import boto3
from botocore.config import Config
import os
import time
import pg8000
from botocore.exceptions import ClientError
import ssl
from datetime import datetime, date
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

_boto_config = Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 1})

bedrock = boto3.client("bedrock-runtime", region_name="ap-south-1", config=_boto_config)
sns = boto3.client("sns", region_name="ap-south-1", config=_boto_config)

RDS_HOST = "wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com"
RDS_PORT = 5432
RDS_DB   = "wealthguard"
RDS_USER = "wealthguard_admin"
RDS_PASS = "os.environ.get("RDS_PASSWORD")"

OPENSEARCH_HOST = os.environ.get("OPENSEARCH_HOST", "vpc-wealthguard-knowledge-fkmsjoivsnq37n2kswhurdnzee.ap-south-1.es.amazonaws.com")
BEDROCK_MODEL = "apac.amazon.nova-lite-v1:0"
SNS_BUDGET_ARN = "arn:aws:sns:ap-south-1:703890345539:wealthguard-budget-alerts"

SECTION_80C_LIMIT = 150000.0
STANDARD_DEDUCTION = 50000.0

NEW_REGIME_SLABS = [
    (300000,  0.00),
    (600000,  0.05),
    (900000,  0.10),
    (1200000, 0.15),
    (1500000, 0.20),
    (float("inf"), 0.30)
]
OLD_REGIME_SLABS = [
    (250000,  0.00),
    (500000,  0.05),
    (1000000, 0.20),
    (float("inf"), 0.30)
]

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

def get_opensearch_client():
    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        "ap-south-1",
        "es",
        session_token=credentials.token
    )
    return OpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=False,
        ssl_show_warn=False,
        connection_class=RequestsHttpConnection
    )

def calculate_tax(income, slabs):
    tax = 0.0
    prev = 0
    for limit, rate in slabs:
        if income <= prev:
            break
        taxable = min(income, limit) - prev
        tax += taxable * rate
        prev = limit
    return round(tax, 2)

def get_user_tax_data(conn, user_id):
    cur = conn.cursor()

    cur.execute("SELECT salary FROM users WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    annual_salary = float(row[0]) * 12 if row and row[0] else 0.0

    cur.execute("""
        SELECT COALESCE(SUM(gross_income), 0), COALESCE(SUM(deductions), 0)
        FROM tax_records
        WHERE user_id = %s
    """, (user_id,))
    tax_row = cur.fetchone()
    gross_income = float(tax_row[0]) if tax_row[0] else 0.0
    invested_80c = float(tax_row[1]) if tax_row[1] else 0.0

    cur.close()

    annual_income = gross_income if gross_income > 0 else annual_salary
    return {
        "annual_income": annual_income,
        "invested_80c": invested_80c
    }

def search_tax_rules(os_client, query):
    try:
        body = {
            "query": {
                "match": {
                    "text": query
                }
            },
            "size": 3
        }
        resp = os_client.search(index="wealthguard-knowledge", body=body)
        hits = resp["hits"]["hits"]
        return [h["_source"].get("text", "")[:300] for h in hits]
    except Exception as e:
        print(f"OpenSearch tax search failed: {e}")
        return []

def call_bedrock(prompt):
    backoff_seconds = [1, 2, 4]
    for attempt in range(3):
        try:
            response = bedrock.invoke_model(
                modelId=BEDROCK_MODEL,
                body=json.dumps({
                    "messages": [{"role": "user", "content": [{"text": prompt}]}],
                    "inferenceConfig": {"maxTokens": 300}
                })
            )
            result = json.loads(response["body"].read())
            return result["output"]["message"]["content"][0]["text"]
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "ThrottlingException" and attempt < 2:
                print(f"Bedrock throttled, retrying in {backoff_seconds[attempt]}s (attempt {attempt+1}/3)")
                time.sleep(backoff_seconds[attempt])
                continue
            print(f"Bedrock call failed: {e}")
            return f"Bedrock unavailable: {str(e)}"
        except Exception as e:
            print(f"Bedrock call failed: {e}")
            return f"Bedrock unavailable: {str(e)}"

def send_january_warning(user_id, message):
    sns.publish(
        TopicArn=SNS_BUDGET_ARN,
        Subject=f"WealthGuard Tax Warning - {user_id}",
        Message=message
    )

def process_user(conn, os_client, user_id):
    tax_data = get_user_tax_data(conn, user_id)
    annual_income = tax_data["annual_income"]
    invested_80c  = tax_data["invested_80c"]
    remaining_80c = max(0, SECTION_80C_LIMIT - invested_80c)

    old_taxable = max(0, annual_income - STANDARD_DEDUCTION - min(invested_80c, SECTION_80C_LIMIT))
    old_tax = calculate_tax(old_taxable, OLD_REGIME_SLABS)

    new_taxable = max(0, annual_income - STANDARD_DEDUCTION)
    new_tax = calculate_tax(new_taxable, NEW_REGIME_SLABS)
    if new_taxable <= 700000:
        new_tax = max(0, new_tax - 25000)

    better_regime = "old" if old_tax < new_tax else "new"
    tax_saving = abs(old_tax - new_tax)

    today = date.today()
    is_january_warning = today.month in [1, 2, 3]

    rag_context = search_tax_rules(os_client, "80C tax saving investment India")

    prompt = f"""You are a tax advisor for Indian individual taxpayers (FY2024-25).

User financials:
- Estimated annual income: Rs.{annual_income:,.0f}
- 80C invested so far: Rs.{invested_80c:,.0f} (limit Rs.1,50,000)
- Remaining 80C room: Rs.{remaining_80c:,.0f}

Tax comparison:
- Old regime tax: Rs.{old_tax:,.0f} (taxable income Rs.{old_taxable:,.0f})
- New regime tax: Rs.{new_tax:,.0f} (taxable income Rs.{new_taxable:,.0f})
- Better regime: {better_regime} (saves Rs.{tax_saving:,.0f})

Current month: {today.strftime("%B")}
Knowledge base: {" ".join(rag_context[:2])}

Give 3 specific tax optimization actions. If January-March, warn about deadline.
Mention specific instruments (ELSS, PPF, NPS, etc). Keep under 200 words."""

    insight = call_bedrock(prompt)

    if is_january_warning and remaining_80c > 0:
        warning_msg = (
            f"Tax deadline warning for user {user_id}. "
            f"80C remaining: Rs.{remaining_80c:,.0f}. "
            f"Better regime: {better_regime}. {insight}"
        )
        send_january_warning(user_id, warning_msg)
        print(f"January warning sent for user {user_id}")

    result = {
        "user_id": user_id,
        "annual_income": annual_income,
        "invested_80c": invested_80c,
        "remaining_80c": remaining_80c,
        "old_regime_tax": old_tax,
        "new_regime_tax": new_tax,
        "better_regime": better_regime,
        "tax_saving": tax_saving,
        "ai_recommendation": insight,
        "source": "bedrock",
        "timestamp": datetime.utcnow().isoformat()
    }
    print(f"User {user_id}: income Rs.{annual_income:,.0f}, better regime={better_regime}, saves Rs.{tax_saving:,.0f}")
    return result

def lambda_handler(event, context):
    print("Tax Optimizer Agent started -", datetime.utcnow().isoformat())
    conn = get_db_conn()
    os_client = get_opensearch_client()
    try:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users")
        users = [r[0] for r in cur.fetchall()]
        cur.close()
        print(f"Processing {len(users)} users")
        results = []
        for user_id in users:
            try:
                r = process_user(conn, os_client, user_id)
                results.append(r)
            except Exception as e:
                print(f"Error processing user {user_id}: {e}")
                results.append({"user_id": user_id, "error": str(e)})
        summary = {
            "processed": len(results),
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }
        return {"statusCode": 200, "body": json.dumps(summary)}
    finally:
        conn.close()

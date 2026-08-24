import os
import json
import boto3
import pg8000
import ssl
import datetime
from botocore.config import Config
from botocore.exceptions import ClientError
import time
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

boto_config = Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 1})

RDS_HOST = "wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com"
RDS_PORT = 5432
RDS_DB = "wealthguard"
RDS_USER = "wealthguard_admin"
RDS_PASS = "os.environ.get("RDS_PASSWORD")"

OPENSEARCH_HOST = "vpc-wealthguard-knowledge-fkmsjoivsnq37n2kswhurdnzee.ap-south-1.es.amazonaws.com"
BEDROCK_MODEL = "apac.amazon.nova-lite-v1:0"
REGION = "ap-south-1"

bedrock = boto3.client("bedrock-runtime", region_name=REGION, config=boto_config)

AMFI_FUNDS = {
    "aggressive": [
        {"name": "Parag Parikh Flexi Cap", "nav": 89.37, "category": "flexi_cap"},
        {"name": "Quant Small Cap Fund", "nav": 245.60, "category": "small_cap"},
        {"name": "Nippon India Small Cap Fund", "nav": 178.22, "category": "small_cap"},
        {"name": "Mirae Asset Emerging Bluechip", "nav": 132.15, "category": "mid_cap"},
        {"name": "SBI Small Cap Fund", "nav": 165.40, "category": "small_cap"},
        {"name": "Axis Midcap Fund", "nav": 98.75, "category": "mid_cap"}
    ],
    "moderate": [
        {"name": "ICICI Prudential Bluechip", "nav": 112.84, "category": "large_cap"},
        {"name": "HDFC Balanced Advantage", "nav": 498.21, "category": "hybrid"},
        {"name": "Mirae Asset Large Cap Fund", "nav": 145.30, "category": "large_cap"},
        {"name": "Kotak Equity Hybrid Fund", "nav": 78.60, "category": "hybrid"},
        {"name": "UTI Nifty Index Fund", "nav": 205.10, "category": "index"},
        {"name": "SBI Bluechip Fund", "nav": 156.90, "category": "large_cap"}
    ],
    "conservative": [
        {"name": "HDFC Corporate Bond Fund", "nav": 32.45, "category": "debt"},
        {"name": "ICICI Prudential Liquid Fund", "nav": 340.20, "category": "debt"},
        {"name": "SBI Magnum Gilt Fund", "nav": 58.90, "category": "debt"},
        {"name": "Axis Treasury Advantage Fund", "nav": 2450.75, "category": "debt"},
        {"name": "Kotak Debt Hybrid Fund", "nav": 45.30, "category": "hybrid"},
        {"name": "HDFC Short Term Debt Fund", "nav": 28.15, "category": "debt"}
    ]
}

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
        REGION,
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

def search_investment_rules(os_client, query):
    try:
        body = {
            "query": {"match": {"text": query}},
            "size": 3
        }
        resp = os_client.search(index="wealthguard-knowledge", body=body)
        hits = resp["hits"]["hits"]
        return [h["_source"].get("text", "")[:300] for h in hits]
    except Exception as e:
        print(f"OpenSearch investment search failed: {e}")
        return []

def call_bedrock(prompt):
    backoff_seconds = [1, 2, 4]
    for attempt in range(3):
        try:
            response = bedrock.invoke_model(
                modelId=BEDROCK_MODEL,
                body=json.dumps({
                    "messages": [{"role": "user", "content": [{"text": prompt}]}],
                    "inferenceConfig": {"maxTokens": 400}
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

def process_user(conn, os_client, user_id):
    cur = conn.cursor()
    cur.execute("SELECT salary, risk_appetite FROM users WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()

    if not row:
        return {"error": "user not found"}

    salary = float(row[0]) if row[0] else 0.0
    risk_appetite = (row[1] or "medium").lower()

    risk_map = {"low": "conservative", "medium": "moderate", "high": "aggressive"}
    risk_bucket = risk_map.get(risk_appetite, "moderate")

    funds = AMFI_FUNDS.get(risk_bucket, AMFI_FUNDS["moderate"])[:3]

    monthly_sip = round(salary * 0.15, 2)

    rag_context = search_investment_rules(os_client, f"{risk_bucket} investment SIP fund allocation")

    prompt = f"""You are an investment advisor for Indian retail investors.

User profile:
- Monthly salary: Rs.{salary:,.0f}
- Risk appetite: {risk_appetite} ({risk_bucket})
- Suggested monthly SIP: Rs.{monthly_sip:,.0f}

Available funds for this risk profile:
{json.dumps(funds, indent=2)}

Knowledge base context: {" ".join(rag_context[:2])}

Recommend how to split the monthly SIP amount across these 3 funds with specific rupee amounts per fund.
Keep the response under 150 words."""

    insight = call_bedrock(prompt)

    return {
        "user_id": user_id,
        "salary": salary,
        "risk_appetite": risk_appetite,
        "risk_bucket": risk_bucket,
        "monthly_sip": monthly_sip,
        "recommended_funds": funds,
        "amfi_funds_fetched": len(funds),
        "ai_recommendation": insight,
        "source": "bedrock",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

def lambda_handler(event, context):
    conn = get_db_conn()
    os_client = get_opensearch_client()
    try:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users")
        users = [r[0] for r in cur.fetchall()]
        cur.close()

        results = []
        for user_id in users:
            try:
                results.append(process_user(conn, os_client, user_id))
            except Exception as e:
                print(f"Error processing user {user_id}: {e}")
                results.append({"user_id": user_id, "error": str(e)})

        return {
            "statusCode": 200,
            "body": json.dumps({
                "processed": len(results),
                "results": results,
                "timestamp": datetime.datetime.utcnow().isoformat()
            })
        }
    finally:
        conn.close()

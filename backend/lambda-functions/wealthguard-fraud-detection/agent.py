import os
import json
import base64
import boto3
import pg8000
import redis
import hashlib
import time
import datetime
from botocore.config import Config
from botocore.exceptions import ClientError

boto_config = Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 1})

RDS_HOST = "wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com"
RDS_DB = "wealthguard"
RDS_USER = "wealthguard_admin"
RDS_PASS = "os.environ.get("RDS_PASSWORD")"

REDIS_HOST = "wealthguard-redis.3vfx2r.0001.aps1.cache.amazonaws.com"
REDIS_PORT = 6379
REDIS_TTL = 300

OPENSEARCH_ENDPOINT = "https://vpc-wealthguard-knowledge-fkmsjoivsnq37n2kswhurdnzee.ap-south-1.es.amazonaws.com"
OPENSEARCH_INDEX = "wealthguard-knowledge"
DYNAMO_TABLE = "wealthguard-fraud-incidents"
SNS_ARN = "arn:aws:sns:ap-south-1:703890345539:wealthguard-fraud-alerts"
REGION = "ap-south-1"

bedrock = boto3.client("bedrock-runtime", region_name=REGION, config=boto_config)
dynamo = boto3.client("dynamodb", region_name=REGION, config=boto_config)
sns = boto3.client("sns", region_name=REGION, config=boto_config)

PRODUCT_CD_MAP = {
    "W": "retail",
    "C": "crypto_cash",
    "S": "services",
    "R": "travel",
    "H": "home_goods"
}


def get_redis():
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, socket_connect_timeout=2, socket_timeout=2, decode_responses=True)
        r.ping()
        return r
    except Exception as e:
        print(f"Redis connection failed: {e}")
        return None


def normalize_txn(transaction):
    normalized = dict(transaction)

    raw_category = str(transaction.get("category", "")).strip()
    if raw_category in PRODUCT_CD_MAP:
        normalized["category"] = PRODUCT_CD_MAP[raw_category]
    elif not raw_category or raw_category.lower() == "unknown":
        normalized["category"] = "unknown"
    else:
        normalized["category"] = raw_category.lower()

    try:
        normalized["amount"] = float(transaction.get("amount", 0) or 0)
    except (ValueError, TypeError):
        normalized["amount"] = 0.0

    if not normalized.get("merchant_name"):
        normalized["merchant_name"] = "Unknown"

    if not normalized.get("location") or normalized.get("location") == "unknown":
        normalized["location"] = "Unknown"

    if not normalized.get("timestamp"):
        normalized["timestamp"] = datetime.datetime.utcnow().isoformat()

    device_type = transaction.get("device_type", "unknown")
    device_info = transaction.get("device_info", "unknown")
    normalized["device_new"] = bool(
        transaction.get("new_device",
            (not device_type or device_type == "unknown") and (not device_info or device_info == "unknown")
        )
    )

    if not normalized.get("transaction_id"):
        normalized["transaction_id"] = "unknown"

    if not normalized.get("card_number"):
        normalized["card_number"] = "unknown"

    return normalized


def embed_text(text):
    resp = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": text}),
        contentType="application/json",
        accept="application/json"
    )
    body = json.loads(resp["body"].read())
    return body["embedding"]


def search_opensearch_rag(query_vector, top_k=3):
    import urllib.request
    import ssl
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest

    session = boto3.Session()
    creds = session.get_credentials().get_frozen_credentials()

    payload = json.dumps({
        "size": top_k,
        "query": {
            "knn": {
                "embedding": {
                    "vector": query_vector,
                    "k": top_k
                }
            }
        },
        "_source": ["text", "category"]
    }).encode("utf-8")

    url = f"{OPENSEARCH_ENDPOINT}/{OPENSEARCH_INDEX}/_search"
    aws_request = AWSRequest(method="POST", url=url, data=payload, headers={"Content-Type": "application/json", "Host": url.split("/")[2]})
    SigV4Auth(creds, "es", REGION).add_auth(aws_request)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, data=payload, headers=dict(aws_request.headers), method="POST")
    with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
        result = json.loads(resp.read())

    hits = result.get("hits", {}).get("hits", [])
    return [h["_source"].get("text", "") for h in hits]


def call_bedrock_with_retry(transaction, rag_chunks):
    rag_text = "\n\n".join([f"Pattern {i+1}: {c}" for i, c in enumerate(rag_chunks)])

    device_note = "This is a NEW/UNRECOGNIZED device for this user." if transaction.get("device_new") else "This is a known device for this user."

    prompt = f"""You are a fraud detection AI for an Indian personal finance app, analyzing transactions from the IEEE-CIS fraud dataset patterns.

Relevant fraud patterns from knowledge base:
{rag_text}

SCORE ANCHORING (follow strictly):
- 0-30: LOW risk, routine transaction, no red flags
- 31-69: MEDIUM risk, some unusual factors but not clearly fraudulent
- 70-85: HIGH risk, multiple red flags present, likely fraudulent
- 86-100: CRITICAL risk, strong fraud indicators, immediate block warranted

CARD-TESTING FRAUD PATTERN (moderate signal only, NOT automatic high-risk):
Fraudsters sometimes test stolen cards with SMALL transactions (Rs.10-500) in crypto or retail
categories. However, a single small transaction with a new/unrecognized device is ALSO very
common for completely legitimate purchases (first purchase on a new card, guest checkout, gift
purchase, etc.) -- this combination ALONE is NOT sufficient evidence of fraud and should NOT
score above 50-55 on its own. Only escalate to HIGH/CRITICAL (70+) if the small-amount pattern
is corroborated by at least one ADDITIONAL red flag: unusual hour (11pm-4am), suspicious
location, or the RAG knowledge base patterns describing velocity/repeated attempts. A single
isolated small transaction with just a new device and nothing else suspicious should typically
score LOW to MEDIUM (20-45), reflecting genuine uncertainty rather than presumed fraud.

Transaction to analyze:
- Amount: Rs.{transaction.get("amount")}
- Merchant: {transaction.get("merchant_name", "Unknown")}
- Category: {transaction.get("category", "Unknown")}
- Location: {transaction.get("location", "Unknown")}
- Time: {transaction.get("timestamp", "Unknown")}
- User ID: {transaction.get("user_id")}
- Device status: {device_note}
- Card Number (last 4): {str(transaction.get("card_number", ""))[-4:]}

Respond ONLY in this exact JSON format:
{{
  "fraud_score": <integer 0-100>,
  "risk_level": "<LOW|MEDIUM|HIGH|CRITICAL>",
  "reasoning": "<2-3 sentence explanation referencing specific transaction details and fraud patterns>",
  "recommended_action": "<ALLOW|REVIEW|BLOCK>"
}}"""

    backoff_seconds = [1, 2, 4]
    last_exception = None

    for attempt in range(3):
        try:
            resp = bedrock.invoke_model(
                modelId="apac.amazon.nova-lite-v1:0",
                body=json.dumps({
                    "messages": [{"role": "user", "content": [{"text": prompt}]}],
                    "inferenceConfig": {"maxTokens": 512}
                }),
                contentType="application/json",
                accept="application/json"
            )
            body = json.loads(resp["body"].read())
            text = body["output"]["message"]["content"][0]["text"].strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            last_exception = e
            if error_code == "ThrottlingException" and attempt < 2:
                print(f"Bedrock throttled, retrying in {backoff_seconds[attempt]}s (attempt {attempt+1}/3)")
                time.sleep(backoff_seconds[attempt])
                continue
            else:
                raise
        except Exception as e:
            last_exception = e
            raise

    raise last_exception


def rule_based_fallback(transaction):
    amount = float(transaction.get("amount", 0))
    score = 0
    if amount > 50000:
        score += 40
    elif amount > 20000:
        score += 25
    elif amount > 10000:
        score += 10
    category = (transaction.get("category") or "").lower()
    # NOTE: reduced from 30 -> 15. Category alone (e.g. crypto_cash from IEEE-CIS ProductCD=C)
    # is common in this dataset and not inherently fraudulent without other signals.
    if category in ["gambling", "crypto", "crypto_cash", "foreign_transfer", "cash", "transfer"]:
        score += 15
    if transaction.get("device_new") and category in ["crypto", "crypto_cash", "retail"] and 10 <= amount <= 500:
        score += 20  # lowered from 50 -- alone this shouldn't cross the 70 threshold
    location = (transaction.get("location") or "").lower()
    # NOTE: "unknown" removed from suspicious-location list -- missing address data is
    # common for legitimate transactions in this dataset and should not be penalized.
    if any(x in location for x in ["tor", "lagos", "minsk"]):
        score += 30
    hour = datetime.datetime.utcnow().hour
    if hour >= 23 or hour <= 4:
        score += 10
    score = min(score, 100)
    risk = "LOW" if score < 31 else "MEDIUM" if score < 70 else "HIGH" if score < 86 else "CRITICAL"
    return {
        "fraud_score": score,
        "risk_level": risk,
        "reasoning": f"Rule-based fallback: amount Rs.{amount}, category {category}, location {location}",
        "recommended_action": "ALLOW" if score < 70 else "REVIEW" if score < 86 else "BLOCK"
    }


def write_dynamo(transaction, result, method):
    incident_id = hashlib.md5(f"{transaction.get('transaction_id')}{time.time()}".encode()).hexdigest()
    dynamo.put_item(
        TableName=DYNAMO_TABLE,
        Item={
            "incident_id": {"S": incident_id},
            "user_id": {"S": str(transaction.get("user_id", "unknown"))},
            "transaction_id": {"S": str(transaction.get("transaction_id", "unknown"))},
            "fraud_score": {"N": str(result["fraud_score"])},
            "risk_level": {"S": result["risk_level"]},
            "reasoning": {"S": result["reasoning"]},
            "recommended_action": {"S": result["recommended_action"]},
            "detection_method": {"S": method},
            "incident_timestamp": {"S": datetime.datetime.utcnow().isoformat()}
        }
    )
    return incident_id


def process_single_transaction(raw_transaction, r):
    transaction = normalize_txn(raw_transaction)
    transaction_id = str(transaction.get("transaction_id", "unknown"))
    redis_key = f"fraud:{transaction_id}"

    if r:
        try:
            cached = r.get(redis_key)
            if cached:
                print(f"Redis cache HIT for transaction {transaction_id}")
                cached_result = json.loads(cached)
                cached_result["detection_method"] = "redis_cache"
                cached_result["cache_hit"] = True
                return cached_result
        except Exception as e:
            print(f"Redis get failed: {e}")

    method = "bedrock_rag"
    result = None

    try:
        tx_text = f"Amount {transaction.get('amount')} merchant {transaction.get('merchant_name')} category {transaction.get('category')} location {transaction.get('location')}"
        vector = embed_text(tx_text)
        rag_chunks = search_opensearch_rag(vector, top_k=3)
        result = call_bedrock_with_retry(transaction, rag_chunks)
        print(f"Bedrock RAG succeeded for {transaction_id}: score={result['fraud_score']}")
    except Exception as e:
        print(f"Bedrock/RAG failed for {transaction_id}: {e} -- using rule-based fallback")
        method = "rule_based_fallback"
        result = rule_based_fallback(transaction)

    incident_id = write_dynamo(transaction, result, method)

    if r:
        try:
            cache_payload = {
                "incident_id": incident_id,
                "fraud_score": result["fraud_score"],
                "risk_level": result["risk_level"],
                "reasoning": result["reasoning"],
                "recommended_action": result["recommended_action"],
                "detection_method": method
            }
            r.setex(redis_key, REDIS_TTL, json.dumps(cache_payload))
        except Exception as e:
            print(f"Redis set failed: {e}")

    score_val = result["fraud_score"]
    if 50 <= score_val < 70:
        try:
            import random
            import string
            otp_code = "".join(random.choices(string.digits, k=6))
            hold_id = f"hold-{transaction_id}-{int(time.time())}"
            dynamo.put_item(
                TableName="wealthguard-review-queue",
                Item={
                    "hold_id": {"S": hold_id},
                    "incident_id": {"S": incident_id},
                    "transaction_id": {"S": transaction_id},
                    "user_id": {"S": str(transaction.get("user_id", "unknown"))},
                    "fraud_score": {"N": str(score_val)},
                    "reasoning": {"S": result["reasoning"]},
                    "otp_code": {"S": otp_code},
                    "status": {"S": "pending"},
                    "created_at": {"S": datetime.datetime.utcnow().isoformat()}
                }
            )
            sns.publish(
                TopicArn=SNS_ARN,
                Subject=f"WealthGuard OTP Verification Required - {transaction_id}",
                Message=json.dumps({
                    "hold_id": hold_id,
                    "incident_id": incident_id,
                    "user_id": transaction.get("user_id"),
                    "fraud_score": score_val,
                    "reasoning": result["reasoning"],
                    "otp_code": otp_code,
                    "instructions": "Reply with this code within 30 seconds to confirm the transaction, or it will be soft-blocked and sent for manual review."
                })
            )
            print(f"OTP hold created: {hold_id}, code sent via SNS")
        except Exception as e:
            print(f"OTP hold/SNS failed: {e}")
    elif result["risk_level"] in ("HIGH", "CRITICAL"):
        try:
            sns.publish(
                TopicArn=SNS_ARN,
                Subject=f"WealthGuard Fraud Alert: {result['risk_level']} risk detected",
                Message=json.dumps({
                    "incident_id": incident_id,
                    "user_id": transaction.get("user_id"),
                    "fraud_score": result["fraud_score"],
                    "reasoning": result["reasoning"],
                    "recommended_action": result["recommended_action"]
                })
            )
        except Exception as e:
            print(f"SNS publish failed: {e}")

    return {
        "incident_id": incident_id,
        "transaction_id": transaction_id,
        "fraud_score": result["fraud_score"],
        "risk_level": result["risk_level"],
        "reasoning": result["reasoning"],
        "recommended_action": result["recommended_action"],
        "detection_method": method,
        "cache_hit": False
    }


def lambda_handler(event, context):
    r = get_redis()

    if isinstance(event, dict) and "Records" in event:
        results = []
        for record in event["Records"]:
            try:
                kinesis_data = record.get("kinesis", {}).get("data", "")
                decoded = base64.b64decode(kinesis_data).decode("utf-8")
                raw_transaction = json.loads(decoded)
                result = process_single_transaction(raw_transaction, r)
                results.append(result)
            except Exception as e:
                print(f"Failed to process Kinesis record: {e}")
                results.append({"error": str(e)})
        return {
            "statusCode": 200,
            "body": json.dumps({"processed": len(results), "results": results})
        }

    body = event if isinstance(event, dict) else json.loads(event.get("body", "{}"))
    raw_transaction = body.get("transaction", body)
    result = process_single_transaction(raw_transaction, r)
    return {"statusCode": 200, "body": json.dumps(result)}

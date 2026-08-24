import json
import boto3
import datetime
from botocore.config import Config

config = Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 1})
dynamo = boto3.client("dynamodb", region_name="ap-south-1", config=config)

REVIEW_TABLE = "wealthguard-review-queue"
FRAUD_TABLE = "wealthguard-fraud-incidents"

def lambda_handler(event, context):
    if isinstance(event, dict) and "body" in event and "httpMethod" in event:
        body = json.loads(event.get("body") or "{}")
    else:
        body = event if isinstance(event, dict) else json.loads(event)
    hold_id = body.get("hold_id")
    otp_code = body.get("otp_code")
    action = body.get("action", "confirm")  # "confirm" or "deny"

    if not hold_id:
        return {"statusCode": 400, "body": json.dumps({"error": "hold_id required"})}

    try:
        resp = dynamo.get_item(
            TableName=REVIEW_TABLE,
            Key={"hold_id": {"S": hold_id}}
        )
        item = resp.get("Item")
        if not item:
            return {"statusCode": 404, "body": json.dumps({"error": "hold not found"})}

        current_status = item.get("status", {}).get("S", "unknown")
        if current_status != "pending":
            return {"statusCode": 409, "body": json.dumps({"error": f"hold already resolved: {current_status}"})}

        stored_otp = item.get("otp_code", {}).get("S", "")

        if action == "confirm":
            if otp_code != stored_otp:
                return {"statusCode": 403, "body": json.dumps({"error": "invalid OTP code"})}
            new_status = "approved"
        elif action == "deny":
            new_status = "denied"
        else:
            return {"statusCode": 400, "body": json.dumps({"error": "action must be confirm or deny"})}

        dynamo.update_item(
            TableName=REVIEW_TABLE,
            Key={"hold_id": {"S": hold_id}},
            UpdateExpression="SET #s = :s, resolved_at = :r",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": {"S": new_status},
                ":r": {"S": datetime.datetime.utcnow().isoformat()}
            }
        )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "hold_id": hold_id,
                "status": new_status,
                "transaction_id": item.get("transaction_id", {}).get("S", ""),
                "message": f"Transaction {new_status}"
            })
        }
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

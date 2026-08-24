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

def months_between(d1, d2):
    return max(1, (d2.year - d1.year) * 12 + (d2.month - d1.month))

def send_goal_alert(user_id, goal_name, extra_needed, revised_deadline):
    message = (
        f"Goal alert for user {user_id}: '{goal_name}' is off track. "
        f"You need an extra Rs.{extra_needed:,.0f}/month to hit your original deadline, "
        f"or your revised completion date is {revised_deadline}."
    )
    sns.publish(
        TopicArn=SNS_BUDGET_ARN,
        Subject=f"WealthGuard Goal Alert - {user_id} - {goal_name}",
        Message=message
    )
    return message

def process_user(conn, user_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT goal_id, goal_name, target_amount, current_amount, target_date, status
        FROM goals
        WHERE user_id = %s AND status = 'active'
    """, (user_id,))
    goals = cur.fetchall()
    cur.close()

    today = datetime.date.today()
    results = []

    for goal_id, goal_name, target_amount, current_amount, target_date, status in goals:
        target_amount = float(target_amount)
        current_amount = float(current_amount)
        remaining_amount = max(0, target_amount - current_amount)
        progress_pct = round((current_amount / target_amount) * 100, 1) if target_amount > 0 else 0

        months_remaining = months_between(today, target_date)
        required_monthly_saving = round(remaining_amount / months_remaining, 2) if months_remaining > 0 else remaining_amount

        assumed_current_monthly_rate = round(current_amount / max(1, months_between(datetime.date(today.year - 1, today.month, 1), today)), 2)

        will_miss_goal = assumed_current_monthly_rate > 0 and assumed_current_monthly_rate < required_monthly_saving

        alert_sent = False
        revised_deadline = None
        extra_needed = 0.0

        if will_miss_goal:
            months_needed_at_current_rate = remaining_amount / assumed_current_monthly_rate if assumed_current_monthly_rate > 0 else None
            if months_needed_at_current_rate:
                revised_date = today + datetime.timedelta(days=int(months_needed_at_current_rate * 30))
                revised_deadline = revised_date.isoformat()
            extra_needed = round(required_monthly_saving - assumed_current_monthly_rate, 2)
            send_goal_alert(user_id, goal_name, extra_needed, revised_deadline)
            alert_sent = True

        results.append({
            "goal_id": goal_id,
            "goal_name": goal_name,
            "target_amount": target_amount,
            "current_amount": current_amount,
            "progress_pct": progress_pct,
            "target_date": str(target_date),
            "required_monthly_saving": required_monthly_saving,
            "will_miss_goal": will_miss_goal,
            "revised_deadline": revised_deadline,
            "extra_monthly_needed": extra_needed,
            "alert_sent": alert_sent
        })

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
        print(f"Unhandled error in goal-tracker: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
    finally:
        conn.close()

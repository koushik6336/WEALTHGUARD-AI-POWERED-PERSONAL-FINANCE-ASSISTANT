import os
import json
import pg8000
import hashlib
import re
import random
import datetime

RDS_HOST = "wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com"
RDS_USER = "wealthguard_admin"
RDS_PASS = "os.environ.get("RDS_PASSWORD")"
RDS_DB = "wealthguard"
RDS_PORT = 5432

headers = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}

def get_conn():
    return pg8000.connect(RDS_USER, host=RDS_HOST, port=RDS_PORT, database=RDS_DB, password=RDS_PASS, ssl_context=True)

def hash_password(password):
    salt = "wealthguard_salt_2024"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

def get_source_ip(event):
    try:
        return event.get("requestContext", {}).get("identity", {}).get("sourceIp")
    except Exception:
        return None

def check_unusual_login(cur, user_id, current_ip):
    if not current_ip:
        return False
    cur.execute("SELECT ip_address FROM login_history WHERE user_id=%s ORDER BY timestamp DESC LIMIT 5", (user_id,))
    recent_ips = [r[0] for r in cur.fetchall() if r[0]]
    if not recent_ips:
        return False
    return current_ip not in recent_ips

def generate_otp():
    return str(random.randint(100000, 999999))

def lambda_handler(event, context):
    method = event.get("httpMethod", "POST")
    path = event.get("path", "")
    body = json.loads(event.get("body") or "{}")
    params = event.get("queryStringParameters") or {}
    source_ip = get_source_ip(event)

    try:
        conn = get_conn()
        conn.autocommit = True
        cur = conn.cursor()

        if path.endswith("/login-history"):
            user_id = params.get("user_id")
            if not user_id:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "user_id required"})}
            cur.execute("SELECT timestamp, ip_address, city FROM login_history WHERE user_id=%s ORDER BY timestamp DESC LIMIT 5", (user_id,))
            history = [{"timestamp": str(r[0]), "ip": r[1], "city": r[2]} for r in cur.fetchall()]
            conn.close()
            return {"statusCode": 200, "headers": headers, "body": json.dumps({"history": history})}

        elif path.endswith("/2fa-status"):
            user_id = params.get("user_id")
            if not user_id:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "user_id required"})}
            cur.execute("SELECT two_factor_enabled FROM users WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
            if not row:
                return {"statusCode": 404, "headers": headers, "body": json.dumps({"error": "User not found"})}
            conn.close()
            return {"statusCode": 200, "headers": headers, "body": json.dumps({"two_factor_enabled": bool(row[0])})}

        elif path.endswith("/signup"):
            user_id = body.get("user_id")
            name = body.get("name")
            email = body.get("email")
            password = body.get("password")

            if not all([user_id, name, email, password]):
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "All fields required"})}

            if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "Invalid email format"})}

            if len(password) < 6:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "Password must be at least 6 characters"})}

            cur.execute("SELECT user_id FROM users WHERE user_id=%s OR email=%s", (user_id, email))
            if cur.fetchone():
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "User ID or email already exists"})}

            password_hash = hash_password(password)
            cur.execute("""
                INSERT INTO users (user_id, name, email, password_hash, email_verified, salary, monthly_budget)
                VALUES (%s, %s, %s, %s, true, 0, 0)
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id, name, email, password_hash))

            conn.close()
            return {"statusCode": 200, "headers": headers, "body": json.dumps({"status": "created", "user_id": user_id, "name": name})}

        elif path.endswith("/enable-2fa"):
            user_id = body.get("user_id")
            if not user_id:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "user_id required"})}

            cur.execute("SELECT user_id FROM users WHERE user_id=%s", (user_id,))
            if not cur.fetchone():
                return {"statusCode": 404, "headers": headers, "body": json.dumps({"error": "User not found"})}

            otp = generate_otp()
            expires = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
            cur.execute(
                "UPDATE users SET verification_token=%s, verification_token_expires=%s WHERE user_id=%s",
                (otp, expires, user_id)
            )
            conn.close()
            return {"statusCode": 200, "headers": headers, "body": json.dumps({"status": "otp_generated", "otp": otp, "expires_in_minutes": 10})}

        elif path.endswith("/verify-2fa"):
            user_id = body.get("user_id")
            otp = body.get("otp")
            if not user_id or not otp:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "user_id and otp required"})}

            cur.execute("SELECT verification_token, verification_token_expires FROM users WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
            if not row:
                return {"statusCode": 404, "headers": headers, "body": json.dumps({"error": "User not found"})}

            stored_otp, expires = row
            if not stored_otp or stored_otp != otp:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "Invalid OTP"})}

            if expires and datetime.datetime.utcnow() > expires:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "OTP expired"})}

            cur.execute(
                "UPDATE users SET two_factor_enabled=true, verification_token=NULL, verification_token_expires=NULL WHERE user_id=%s",
                (user_id,)
            )
            conn.close()
            return {"statusCode": 200, "headers": headers, "body": json.dumps({"status": "2fa_enabled"})}

        elif path.endswith("/login"):
            user_id = body.get("user_id")
            password = body.get("password")
            otp = body.get("otp")

            if not user_id:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "user_id required"})}

            cur.execute("SELECT user_id, name, password_hash, two_factor_enabled, verification_token, verification_token_expires FROM users WHERE user_id=%s", (user_id,))
            row = cur.fetchone()

            if not row:
                return {"statusCode": 401, "headers": headers, "body": json.dumps({"error": "Invalid credentials"})}

            db_user_id, name, stored_hash, two_factor_enabled, stored_otp, otp_expires = row

            if otp is not None:
                if not stored_otp or stored_otp != otp:
                    return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "Invalid OTP"})}
                if otp_expires and datetime.datetime.utcnow() > otp_expires:
                    return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "OTP expired"})}

                cur.execute("UPDATE users SET verification_token=NULL, verification_token_expires=NULL WHERE user_id=%s", (user_id,))
                unusual = check_unusual_login(cur, user_id, source_ip)
                cur.execute("INSERT INTO login_history (user_id, timestamp, ip_address) VALUES (%s, NOW(), %s)", (user_id, source_ip))
                conn.close()
                return {"statusCode": 200, "headers": headers, "body": json.dumps({"status": "ok", "user_id": db_user_id, "name": name, "unusual_login": unusual})}

            if not password:
                return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "password required"})}

            if not stored_hash:
                if two_factor_enabled:
                    otp_val = generate_otp()
                    expires = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
                    cur.execute("UPDATE users SET verification_token=%s, verification_token_expires=%s WHERE user_id=%s", (otp_val, expires, user_id))
                    conn.close()
                    return {"statusCode": 200, "headers": headers, "body": json.dumps({"requires_2fa": True, "user_id": db_user_id, "name": name, "otp": otp_val})}

                unusual = check_unusual_login(cur, user_id, source_ip)
                cur.execute("INSERT INTO login_history (user_id, timestamp, ip_address) VALUES (%s, NOW(), %s)", (user_id, source_ip))
                conn.close()
                return {"statusCode": 200, "headers": headers, "body": json.dumps({"status": "ok", "user_id": db_user_id, "name": name, "needs_password": True, "unusual_login": unusual})}

            if hash_password(password) != stored_hash:
                return {"statusCode": 401, "headers": headers, "body": json.dumps({"error": "Invalid credentials"})}

            if two_factor_enabled:
                otp_val = generate_otp()
                expires = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
                cur.execute("UPDATE users SET verification_token=%s, verification_token_expires=%s WHERE user_id=%s", (otp_val, expires, user_id))
                conn.close()
                return {"statusCode": 200, "headers": headers, "body": json.dumps({"requires_2fa": True, "user_id": db_user_id, "name": name, "otp": otp_val})}

            unusual = check_unusual_login(cur, user_id, source_ip)
            cur.execute("INSERT INTO login_history (user_id, timestamp, ip_address) VALUES (%s, NOW(), %s)", (user_id, source_ip))
            conn.close()
            return {"statusCode": 200, "headers": headers, "body": json.dumps({"status": "ok", "user_id": db_user_id, "name": name, "unusual_login": unusual})}

        else:
            return {"statusCode": 404, "headers": headers, "body": json.dumps({"error": "Not found"})}

    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}

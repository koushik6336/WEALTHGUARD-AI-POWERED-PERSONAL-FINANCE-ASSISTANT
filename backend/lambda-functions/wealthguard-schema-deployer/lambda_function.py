import os
import json
import pg8000
import ssl
import traceback

def lambda_handler(event, context):
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        conn = pg8000.connect(
            "wealthguard_admin",
            host="wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com",
            port=5432,
            database="wealthguard",
            password="os.environ.get("RDS_PASSWORD")",
            ssl_context=ssl_context
        )
        cursor = conn.cursor()

        cursor.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id VARCHAR(10) PRIMARY KEY,
            name VARCHAR(100), email VARCHAR(100),
            salary NUMERIC(12,2), city VARCHAR(50),
            risk_profile VARCHAR(20), risk_appetite VARCHAR(20),
            monthly_budget NUMERIC(12,2),
            created_at TIMESTAMP DEFAULT NOW())""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS transactions (
            transaction_id VARCHAR(50) PRIMARY KEY,
            user_id VARCHAR(10) REFERENCES users(user_id),
            amount NUMERIC(12,2), category VARCHAR(50),
            merchant VARCHAR(100), transaction_date TIMESTAMP,
            status VARCHAR(20), created_at TIMESTAMP DEFAULT NOW())""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS budgets (
            budget_id SERIAL PRIMARY KEY,
            user_id VARCHAR(10) REFERENCES users(user_id),
            category VARCHAR(50), monthly_limit NUMERIC(12,2),
            created_at TIMESTAMP DEFAULT NOW())""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS goals (
            goal_id SERIAL PRIMARY KEY,
            user_id VARCHAR(10) REFERENCES users(user_id),
            goal_name VARCHAR(100), target_amount NUMERIC(12,2),
            current_amount NUMERIC(12,2) DEFAULT 0,
            target_date DATE, status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT NOW())""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS investments (
            investment_id SERIAL PRIMARY KEY,
            user_id VARCHAR(10) REFERENCES users(user_id),
            investment_type VARCHAR(50), amount NUMERIC(12,2),
            purchase_date DATE, current_value NUMERIC(12,2),
            created_at TIMESTAMP DEFAULT NOW())""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS tax_records (
            tax_id SERIAL PRIMARY KEY,
            user_id VARCHAR(10) REFERENCES users(user_id),
            financial_year VARCHAR(10), gross_income NUMERIC(12,2),
            deductions NUMERIC(12,2), tax_paid NUMERIC(12,2),
            created_at TIMESTAMP DEFAULT NOW())""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS fraud_alerts (
            alert_id SERIAL PRIMARY KEY,
            user_id VARCHAR(10) REFERENCES users(user_id),
            transaction_id VARCHAR(50), alert_type VARCHAR(50),
            severity VARCHAR(20), description TEXT,
            created_at TIMESTAMP DEFAULT NOW())""")

        cursor.execute("""INSERT INTO users (user_id, name, email, salary, city, risk_profile, risk_appetite, monthly_budget)
            VALUES
            ('u001','Amit Sharma','amit@example.com',120000,'Mumbai','moderate','medium',40000),
            ('u002','Priya Patel','priya@example.com',95000,'Ahmedabad','conservative','low',30000),
            ('u003','Rahul Gupta','rahul@example.com',150000,'Delhi','aggressive','high',50000),
            ('u004','Sneha Reddy','sneha@example.com',80000,'Hyderabad','moderate','medium',25000),
            ('u005','Karan Singh','karan@example.com',200000,'Bangalore','aggressive','high',70000)
            ON CONFLICT (user_id) DO NOTHING""")

        conn.commit()

        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
        tables = [t[0] for t in cursor.fetchall()]

        cursor.execute("SELECT user_id, name, city FROM users ORDER BY user_id")
        users = cursor.fetchall()

        cursor.close()
        conn.close()

        return {"statusCode": 200, "body": json.dumps({
            "tables": tables, "table_count": len(tables),
            "users": [list(u) for u in users], "user_count": len(users)
        })}

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e), "trace": traceback.format_exc()})}

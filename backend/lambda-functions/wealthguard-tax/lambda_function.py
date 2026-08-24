import os
import json
import pg8000

RDS_HOST = "wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com"
RDS_USER = "wealthguard_admin"
RDS_PASS = "os.environ.get("RDS_PASSWORD")"
RDS_DB = "wealthguard"
RDS_PORT = 5432

headers = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}

def get_conn():
    return pg8000.connect(RDS_USER, host=RDS_HOST, port=RDS_PORT, database=RDS_DB, password=RDS_PASS, ssl_context=True)

def calc_old_regime(income):
    slabs = [(250000,0),(250000,0.05),(500000,0.2),(float('inf'),0.3)]
    tax = 0
    remaining = max(0, income - 50000)  # standard deduction
    for slab, rate in slabs:
        if remaining <= 0: break
        taxable = min(remaining, slab)
        tax += taxable * rate
        remaining -= taxable
    return round(tax)

def calc_new_regime(income):
    slabs = [(300000,0),(400000,0.05),(300000,0.1),(300000,0.15),(300000,0.2),(float('inf'),0.3)]
    tax = 0
    remaining = max(0, income - 75000)  # standard deduction new regime
    for slab, rate in slabs:
        if remaining <= 0: break
        taxable = min(remaining, slab)
        tax += taxable * rate
        remaining -= taxable
    return round(tax)

def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}
    user_id = params.get("user_id")
    if not user_id:
        return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "user_id required"})}
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT salary FROM users WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        if not row:
            return {"statusCode": 404, "headers": headers, "body": json.dumps({"error": "user not found"})}
        annual_salary = float(row[0]) * 12

        cur.execute("SELECT COALESCE(SUM(section_80c_used),0) FROM tax_records WHERE user_id=%s", (user_id,))
        row2 = cur.fetchone()
        invested_80c = float(row2[0]) if row2 else 0
        remaining_80c = max(0, 150000 - invested_80c)

        old_taxable = max(0, annual_salary - 50000 - min(invested_80c, 150000))
        old_tax = calc_old_regime(old_taxable + 50000 - min(invested_80c,150000))
        new_tax = calc_new_regime(annual_salary)

        better = "New" if new_tax <= old_tax else "Old"
        savings = abs(old_tax - new_tax)

        conn.close()
        return {"statusCode": 200, "headers": headers, "body": json.dumps({
            "annual_salary": annual_salary,
            "invested_80c": invested_80c,
            "remaining_80c": remaining_80c,
            "old_regime_tax": old_tax,
            "new_regime_tax": new_tax,
            "recommended_regime": better,
            "savings": savings
        })}
    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}

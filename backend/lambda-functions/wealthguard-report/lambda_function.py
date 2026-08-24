import os
import json
import pg8000
from datetime import datetime, date

RDS_HOST = "wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com"
RDS_USER = "wealthguard_admin"
RDS_PASS = "os.environ.get("RDS_PASSWORD")"
RDS_DB = "wealthguard"
RDS_PORT = 5432

headers = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}

def get_conn():
    return pg8000.connect(RDS_USER, host=RDS_HOST, port=RDS_PORT, database=RDS_DB, password=RDS_PASS, ssl_context=True)

def month_start(year, month):
    return date(year, month, 1)

def prev_month(year, month):
    if month == 1:
        return year - 1, 12
    return year, month - 1

def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}
    user_id = params.get("user_id")
    month_param = params.get("month")  # YYYY-MM, optional

    if not user_id:
        return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "user_id required"})}

    try:
        if month_param:
            req_year, req_month = int(month_param[:4]), int(month_param[5:7])
        else:
            today = datetime.now()
            req_year, req_month = today.year, today.month

        req_month_start = month_start(req_year, req_month)
        py, pm = prev_month(req_year, req_month)
        prev_month_start = month_start(py, pm)

        conn = get_conn()
        conn.autocommit = True
        cur = conn.cursor()

        # User info
        cur.execute("SELECT name, salary, monthly_budget FROM users WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        if not row:
            return {"statusCode": 404, "headers": headers, "body": json.dumps({"error": "user not found"})}
        name, salary, monthly_budget = row[0], float(row[1]) if row[1] else 0, float(row[2]) if row[2] else 0
        annual_salary = salary * 12

        # Budget for requested month (real historical data via spend_entries.date)
        cur.execute("""
            SELECT category, COALESCE(SUM(amount),0) FROM spend_entries
            WHERE user_id=%s AND DATE_TRUNC('month', date) = DATE_TRUNC('month', %s::date)
            GROUP BY category ORDER BY SUM(amount) DESC
        """, (user_id, req_month_start))
        spend_by_cat = [{"category": r[0], "spent": float(r[1])} for r in cur.fetchall()]
        total_spent = sum(s["spent"] for s in spend_by_cat)

        # Budget for previous month (for comparison, also from real spend_entries data)
        cur.execute("""
            SELECT COALESCE(SUM(amount),0) FROM spend_entries
            WHERE user_id=%s AND DATE_TRUNC('month', date) = DATE_TRUNC('month', %s::date)
        """, (user_id, prev_month_start))
        prev_total_spent = float(cur.fetchone()[0])

        # Investments (current live totals - only meaningful for "current", not historical)
        cur.execute("SELECT scheme_name, amount_invested, current_value FROM investments WHERE user_id=%s", (user_id,))
        holdings = []
        total_invested = 0
        total_current = 0
        for r in cur.fetchall():
            inv = float(r[1]) if r[1] else 0
            cur_val = float(r[2]) if r[2] else 0
            total_invested += inv
            total_current += cur_val
            ret = round(((cur_val - inv) / inv * 100), 1) if inv > 0 else 0
            holdings.append({"scheme_name": r[0], "amount_invested": inv, "current_value": cur_val, "return_pct": ret})
        overall_return = round(((total_current - total_invested) / total_invested * 100), 1) if total_invested > 0 else 0

        # Goals (current live totals)
        cur.execute("SELECT goal_name, target_amount, current_amount FROM goals WHERE user_id=%s AND status='active'", (user_id,))
        goals = []
        for r in cur.fetchall():
            target = float(r[1])
            current = float(r[2]) if r[2] else 0
            pct = round((current / target * 100), 1) if target > 0 else 0
            goals.append({"goal_name": r[0], "target_amount": target, "current_amount": current, "progress_pct": pct})

        # Tax
        cur.execute("SELECT COALESCE(SUM(section_80c_used),0) FROM tax_records WHERE user_id=%s", (user_id,))
        invested_80c = float(cur.fetchone()[0])
        remaining_80c = max(0, 150000 - invested_80c)

        # If requested month is the current calendar month, write/update a snapshot for it
        today = datetime.now()
        is_current_month = (req_year == today.year and req_month == today.month)
        if is_current_month:
            cur.execute("""
                INSERT INTO portfolio_snapshots (user_id, snapshot_month, total_spent, total_invested, total_current_value, goals_json)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, snapshot_month)
                DO UPDATE SET total_spent = EXCLUDED.total_spent,
                              total_invested = EXCLUDED.total_invested,
                              total_current_value = EXCLUDED.total_current_value,
                              goals_json = EXCLUDED.goals_json,
                              created_at = NOW()
            """, (user_id, req_month_start, total_spent, total_invested, total_current, json.dumps(goals)))

        # Look up previous month's snapshot for investments/goals comparison
        cur.execute("""
            SELECT total_spent, total_invested, total_current_value, goals_json
            FROM portfolio_snapshots WHERE user_id=%s AND snapshot_month=%s
        """, (user_id, prev_month_start))
        prev_row = cur.fetchone()

        comparison = {
            "has_previous_data": prev_row is not None,
            "previous_month": f"{py:04d}-{pm:02d}",
            "budget": {
                "previous_total_spent": prev_total_spent,
                "delta": round(total_spent - prev_total_spent, 2),
            }
        }
        if prev_row:
            prev_spent_snap, prev_invested, prev_current_val, prev_goals_json = prev_row
            comparison["investments"] = {
                "previous_total_invested": float(prev_invested) if prev_invested else 0,
                "previous_total_current_value": float(prev_current_val) if prev_current_val else 0,
                "delta_current_value": round(total_current - (float(prev_current_val) if prev_current_val else 0), 2),
            }
            prev_goals = json.loads(prev_goals_json) if prev_goals_json else []
            prev_goals_by_name = {g["goal_name"]: g for g in prev_goals}
            goals_comparison = []
            for g in goals:
                prev_g = prev_goals_by_name.get(g["goal_name"])
                goals_comparison.append({
                    "goal_name": g["goal_name"],
                    "previous_progress_pct": prev_g["progress_pct"] if prev_g else None,
                    "delta_progress_pct": round(g["progress_pct"] - prev_g["progress_pct"], 1) if prev_g else None,
                })
            comparison["goals"] = goals_comparison
        else:
            comparison["investments"] = None
            comparison["goals"] = None

        conn.close()
        return {"statusCode": 200, "headers": headers, "body": json.dumps({
            "name": name,
            "annual_salary": annual_salary,
            "monthly_salary": salary,
            "month": f"{req_year:04d}-{req_month:02d}",
            "budget": {"total_spent": total_spent, "by_category": spend_by_cat},
            "investments": {"total_invested": total_invested, "total_current_value": total_current, "overall_return_pct": overall_return, "holdings": holdings},
            "goals": goals,
            "tax": {"annual_salary": annual_salary, "invested_80c": invested_80c, "remaining_80c": remaining_80c},
            "comparison": comparison,
            "generated_at": datetime.now().isoformat()
        })}
    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}

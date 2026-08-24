import os
import json, pg8000

def lambda_handler(event, context):
    conn = pg8000.connect(
        user="wealthguard_admin",
        host="wealthguard-db.ct0ok04sc6y7.ap-south-1.rds.amazonaws.com",
        port=5432,
        database="wealthguard",
        password="os.environ.get("RDS_PASSWORD")",
        ssl_context=True
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(event.get("sql"))
    try:
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return {"statusCode": 200, "body": json.dumps({"columns": cols, "rows": rows})}
    except:
        return {"statusCode": 200, "body": json.dumps({"message": "done"})}

#!/usr/bin/env python3
from datetime import datetime, timezone
from app.integrations.paypal_client import PayPalClient
from app.db.dynamodb import DynamoRepository

def main():
    client = PayPalClient()
    repo = DynamoRepository()
    txns = client.search_transactions_last_hour()
    simplified = [{"date": t.get("date"), "email": t.get("email"), "amount": t.get("amount")} for t in txns]
    print(simplified)

    # Insert into DynamoDB if email doesn't exist; use transaction initiation date for timestamp
    for t in txns:
        email = (t.get("email") or "").strip().lower()
        if not email:
            continue
        # Parse transaction_initiation_date (ISO8601 with offset, without colon in offset per PayPal)
        # Example: 2025-10-17T01:23:45+0000 or 2025-10-16T21:23:45-0400
        raw = t.get("date")
        if not raw:
            continue
        try:
            # Normalize offset string: Python's %z accepts "+HHMM" already
            dt = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S%z")
            utc_day = dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            # If parsing fails, fallback to today's UTC date
            utc_day = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Only insert if not exists
        if not repo._exists_sync(email):  # safe here in a short-lived script; avoids extra thread hop
            repo._put_item_with_timestamp_sync(email, True, utc_day)

if __name__ == "__main__":
    main()

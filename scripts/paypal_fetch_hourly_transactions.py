#!/usr/bin/env python3
from app.integrations.paypal_client import PayPalClient

def main():
    client = PayPalClient()
    txns = client.search_transactions_last_hour()
    simplified = [{"date": t.get("date"), "email": t.get("email"), "amount": t.get("amount")} for t in txns]
    print(simplified)

if __name__ == "__main__":
    main()

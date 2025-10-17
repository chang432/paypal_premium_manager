#!/usr/bin/env python3
from app.integrations.paypal_client import PayPalClient

def main():
    client = PayPalClient()
    token = client.get_access_token(force_refresh=True)
    print("Refreshed PayPal access token (masked):", token[:6] + "...")

if __name__ == "__main__":
    main()

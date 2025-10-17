import base64
import time
from datetime import datetime, timedelta, timezone
import os
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from app.core.config import settings


class PayPalClient:
    """Minimal PayPal REST API client for OAuth and transaction search.

    Note: This uses blocking requests; for occasional cron jobs this is acceptable.
    """

    def __init__(self,
                 client_id: Optional[str] = None,
                 client_secret: Optional[str] = None,
                 base_url: Optional[str] = None):
        self.client_id = client_id or settings.paypal_client_id
        self.client_secret = client_secret or settings.paypal_client_secret
        self.base_url = (base_url or settings.paypal_base_url).rstrip("/")
        if not self.client_id or not self.client_secret:
            raise RuntimeError("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be set")

        self._access_token = None  # type: Optional[str]
        self._token_expiry = 0.0   # type: float
        self._token_scopes = None  # type: Optional[str]
        self._debug = os.getenv("PAYPAL_DEBUG") not in (None, "", "0", "false", "False")

    def get_access_token(self, force_refresh: bool = False) -> str:
        if not force_refresh and self._access_token and time.time() < self._token_expiry - 60:
            if self._access_token is None:
                raise RuntimeError("Access token is not available")
            return self._access_token

        token_url = f"{self.base_url}/v1/oauth2/token"
        auth = (self.client_id, self.client_secret)
        data = {"grant_type": "client_credentials"}
        resp = requests.post(token_url, data=data, auth=auth, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
        self._access_token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 28800))  # default 8h
        self._token_expiry = time.time() + expires_in
        self._token_scopes = payload.get("scope")
        if self._debug:
            print("[PayPal] Issued token; scopes:", self._token_scopes, "expires_in:", expires_in)
        return self._access_token

    def search_transactions_last_hour(self) -> List[Dict]:
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=24)
        return self.search_transactions(start_time, now)

    def search_transactions(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        # Use America/New_York timezone and output like 2014-07-12T00:00:00-0700 (offset without colon)
        ny_tz = ZoneInfo("America/New_York")

        def fmt(dt: datetime) -> str:
            return dt.astimezone(ny_tz).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S%z")

        token = self.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "start_date": fmt(start_time),
            "end_date": fmt(end_time),
            "fields": "all",
            "page_size": 100
        }
        url = f"{self.base_url}/v1/reporting/transactions"
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            detail = None
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            msg = f"PayPal transaction search failed: {resp.status_code} {detail}"
            if self._debug:
                print("[PayPal]", msg)
            raise
        data = resp.json()

        # Normalize a list of {date, email, amount}
        items: List[Dict] = []
        txns = data.get("transaction_details", [])
        for t in txns:
            payer_info = t.get("payer_info", {})
            payer_email = payer_info.get("email_address")
            tx_info = t.get("transaction_info", {})
            amount = None
            amt = tx_info.get("transaction_amount") or {}
            if "value" in amt:
                amount = f"{amt.get('value')} {amt.get('currency_code', '')}".strip()
            # Use transaction initiation/creation time
            date = tx_info.get("transaction_initiation_date") or tx_info.get("transaction_updated_date")
            items.append({
                "date": date,
                "email": payer_email,
                "amount": amount,
            })
        return items

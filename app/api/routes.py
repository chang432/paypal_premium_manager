from fastapi import APIRouter, HTTPException, Request, status
from pydantic import EmailStr
from app.models.schemas import PremiumCheckRequest, PremiumCheckResponse
from app.db.redis_cache import RedisCache
from app.db.dynamodb import DynamoRepository
from app.core.config import settings
from app.integrations.paypal_client import PayPalClient

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/premium/check", response_model=PremiumCheckResponse)
async def premium_check(payload: PremiumCheckRequest):
    cache = RedisCache()
    repo = DynamoRepository()

    # Check cache first
    cached = await cache.get_premium(payload.email)
    if cached is not None:
        return PremiumCheckResponse(email=payload.email, premium=cached, source="cache")

    # Fallback to DB
    try:
        premium = await repo.is_premium(payload.email)
    except Exception:
        # Upstream issue (AWS), surface as 503 for caller to decide retries
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    # Update cache (fire-and-forget)
    try:
        await cache.set_premium(payload.email, premium)
    except Exception:
        # Cache failure should not fail the request
        pass

    return PremiumCheckResponse(email=payload.email, premium=premium, source="db")


@router.get("/premium/check", response_model=PremiumCheckResponse)
async def premium_check_get(email: EmailStr):
    cache = RedisCache()
    repo = DynamoRepository()

    cached = await cache.get_premium(email)
    if cached is not None:
        return PremiumCheckResponse(email=email, premium=cached, source="cache")

    try:
        premium = await repo.is_premium(email)
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        await cache.set_premium(email, premium)
    except Exception:
        pass

    return PremiumCheckResponse(email=email, premium=premium, source="db")


@router.post("/webhooks/paypal")
async def paypal_webhook(request: Request):
    # Parse webhook, resolve payer email via order_id, and upsert into DynamoDB
    try:
        raw = await request.body()
    except Exception:
        raw = b""

    headers = dict(request.headers)
    interesting_keys = [
        "paypal-transmission-id",
        "paypal-transmission-time",
        "paypal-transmission-sig",
        "paypal-cert-url",
        "paypal-auth-algo",
        "content-type",
        "user-agent",
    ]
    interesting = {k: headers.get(k) for k in interesting_keys if k in headers}

    body_text = raw.decode("utf-8", errors="replace")
    if len(body_text) > 4000:
        body_preview = body_text[:4000] + "…"
    else:
        body_preview = body_text

    # print("[PayPal Webhook] method=", request.method, "url=", str(request.url))
    # print("[PayPal Webhook] headers=", interesting)

    # Try to detect event_type and parse JSON payload
    event_type = None
    try:
        import json
        payload = json.loads(body_text) if body_text else {}
        event_type = payload.get("event_type")
    except Exception:
        payload = {}
    print("[PayPal Webhook] event_type=", event_type)

    # Extract order_id if present: resource.supplementary_data.related_ids.order_id
    order_id = None
    try:
        order_id = (
            payload.get("resource", {})
                   .get("supplementary_data", {})
                   .get("related_ids", {})
                   .get("order_id")
            if isinstance(payload, dict) else None
        )
        if isinstance(order_id, str) and order_id:
            print("[PayPal Webhook] order_id=", order_id)
    except Exception:
        order_id = None

    # Derive UTC date string YYYY-MM-DD from resource.create_time (fallback: today's UTC date)
    from datetime import datetime, timezone
    date_str = None
    try:
        r_create = (
            payload.get("resource", {}).get("create_time")
            if isinstance(payload, dict) else None
        )
        if isinstance(r_create, str) and r_create:
            dt = None
            try:
                # canonical Z format
                dt = datetime.strptime(r_create, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except Exception:
                try:
                    # fallback: ISO8601 with offset
                    dt = datetime.fromisoformat(r_create.replace("Z", "+00:00")).astimezone(timezone.utc)
                except Exception:
                    dt = None
            if dt is not None:
                date_str = dt.strftime("%Y-%m-%d")
    except Exception:
        date_str = None
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Resolve payer email: prefer order lookup; fallback to webhook payload
    email = None
    try:
        if isinstance(order_id, str) and order_id:
            client = PayPalClient()
            email = client.get_payer_email_by_order_id(order_id)
    except Exception:
        email = None
    if not email:
        try:
            email = (
                payload.get("resource", {})
                       .get("payer", {})
                       .get("email_address")
                if isinstance(payload, dict) else None
            )
        except Exception:
            email = None

    if not email or not isinstance(email, str):
        print("[PayPal Webhook] No payer email found; skipping DB upsert")
        return {"status": "ok", "skipped": True}

    # Upsert into DynamoDB with timestamp
    repo = DynamoRepository()
    try:
        if await repo.exists(email):
            await repo.update_timestamp(email, date_str)
            action = "updated"
        else:
            await repo.put_user_with_timestamp(email, True, date_str)
            action = "created"
    except Exception as e:
        # Avoid failing the webhook; log and return ok
        print("[PayPal Webhook] DynamoDB upsert failed:", repr(e))
        return {"status": "ok", "error": "dynamodb"}

    return {"status": "ok", "email": email, "date": date_str, "action": action}

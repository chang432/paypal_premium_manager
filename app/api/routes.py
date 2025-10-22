from fastapi import APIRouter, HTTPException, Request, status
from pydantic import EmailStr
from app.models.schemas import PremiumCheckRequest, PremiumCheckResponse
from app.db.redis_cache import RedisCache
from app.db.dynamodb import DynamoRepository
from app.core.config import settings

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
    # For now, just print out request details and return ok
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

    # Try to detect event_type from JSON for convenience
    event_type = None
    try:
        import json
        payload = json.loads(body_text) if body_text else {}
        event_type = payload.get("event_type")
    except Exception:
        payload = {}
    print("[PayPal Webhook] event_type=", event_type)

    # Extract and print order_id if present: resource.supplementary_data.related_ids.order_id
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
        pass

    # Extract and print UTC month/day/year from resource.create_time if present
    try:
        from datetime import datetime, timezone
        r_create = (
            payload.get("resource", {}).get("create_time")
            if isinstance(payload, dict) else None
        )
        if isinstance(r_create, str) and r_create:
            dt = None
            try:
                # canonical Zulu format
                dt = datetime.strptime(r_create, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except Exception:
                try:
                    # fallback: ISO8601 with offset
                    dt = datetime.fromisoformat(r_create.replace("Z", "+00:00")).astimezone(timezone.utc)
                except Exception:
                    dt = None
            if dt is not None:
                print(
                    "[PayPal Webhook] resource.create_time UTC:",
                    {"month": dt.month, "day": dt.day, "year": dt.year},
                )
    except Exception:
        # keep webhook resilient; avoid failing logging
        pass
    # print("[PayPal Webhook] body=", body_preview)

    return {"status": "ok"}

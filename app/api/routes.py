from fastapi import APIRouter, HTTPException, status
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

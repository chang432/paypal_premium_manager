from pydantic import BaseModel, EmailStr


class PremiumCheckRequest(BaseModel):
    email: EmailStr


class PremiumCheckResponse(BaseModel):
    email: EmailStr
    premium: bool
    source: str  # cache or db

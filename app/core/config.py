from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "kofi-premium-manager"
    environment: str = Field(default="dev", validation_alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # API
    api_prefix: str = Field(default="/v1", validation_alias="API_PREFIX")

    # Redis
    redis_url: str = Field(default="redis://redis:6379/0", validation_alias="REDIS_URL")
    redis_ttl_seconds: int = Field(default=3600, validation_alias="REDIS_TTL_SECONDS")

    # AWS / DynamoDB
    aws_region: str = Field(default="us-east-1", validation_alias="AWS_REGION")
    dynamodb_table: str = Field(default="kofi_premium_users", validation_alias="DYNAMODB_TABLE")

    # PayPal
    paypal_client_id: Optional[str] = Field(default=None, validation_alias="PAYPAL_CLIENT_ID")
    paypal_client_secret: Optional[str] = Field(default=None, validation_alias="PAYPAL_CLIENT_SECRET")
    paypal_base_url: str = Field(default="https://api-m.sandbox.paypal.com", validation_alias="PAYPAL_BASE_URL")
    # RFC3339 offset for request timestamps, e.g. "+0000" (UTC) or "-0700"
    paypal_tz_offset: str = Field(default="-0500", validation_alias="PAYPAL_TZ_OFFSET")


settings = Settings()  # type: ignore

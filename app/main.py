import uvicorn
from fastapi import FastAPI
from app.api.routes import router
from app.core.config import settings
from app.db.dynamodb import ensure_table_exists

app = FastAPI(title=settings.app_name)
app.include_router(router, prefix=settings.api_prefix)


@app.on_event("startup")
async def _startup():
    # Ensure DynamoDB table exists at startup (idempotent)
    ensure_table_exists(settings.dynamodb_table, settings.aws_region)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=False)

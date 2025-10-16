import uvicorn
from fastapi import FastAPI
from app.api.routes import router
from app.core.config import settings

app = FastAPI(title=settings.app_name)
app.include_router(router, prefix=settings.api_prefix)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=False)

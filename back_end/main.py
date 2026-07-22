from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from back_end.config import settings


app = FastAPI(
    title="Backend API",
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, object]:
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "debug": settings.debug,
        "base_upload_url": settings.base_upload_url,
        "upload_dir": str(settings.upload_dir),
    }

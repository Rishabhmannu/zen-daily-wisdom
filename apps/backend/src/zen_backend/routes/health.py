from fastapi import APIRouter

from zen_backend.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "environment": settings.environment,
        "checks": {
            "supabase_configured": bool(settings.supabase_url and settings.supabase_service_role_key),
            "gemini_configured": bool(settings.gemini_api_key),
        },
    }


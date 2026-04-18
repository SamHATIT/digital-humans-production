"""
Config endpoints — expose runtime deployment capabilities to the frontend.

C-4 (session3 / Agent C). Résout N35, N41.

The frontend polls `/api/config/capabilities` on boot to decide whether to
render the "Start BUILD" button (only visible when build_enabled=true).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/capabilities")
async def get_capabilities():
    """
    Return the active deployment profile and the feature gates it implies.

    Response shape:
        {
            "profile": "cloud" | "on-premise" | "freemium",
            "build_enabled": bool,
            "providers": {"local/ollama": bool, "anthropic": bool, "openai": bool}
        }
    """
    from app.services.llm_router_service import get_llm_router

    router_instance = get_llm_router()
    return {
        "profile": router_instance.get_active_profile(),
        "build_enabled": router_instance.is_build_enabled(),
        "providers": router_instance.get_available_providers(),
    }

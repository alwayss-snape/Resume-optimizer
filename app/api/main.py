"""The web app (P5.1): `uvicorn app.api.main:app`.

Serves the JSON/SSE API under /api and, once it's built, the React app
from web/dist. The service factory is swappable so tests can run the full
flow without an LLM or LibreOffice.
"""
import os
from typing import Callable, Optional

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.api.routes import SESSION_COOKIE, RateLimiter, router
from app.api.sessions import SessionStore
from app.config.settings import settings

WEB_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "web", "dist")


def default_service(model: Optional[str] = None):
    from app.llm.client import LLMClient
    from app.services.tailor import TailorService

    return TailorService(llm_client=LLMClient(model=model) if model else None)


def create_app(make_service: Callable = default_service, sessions: Optional[SessionStore] = None,
               rate_limit: Optional[int] = None, serve_web: bool = True) -> FastAPI:
    app = FastAPI(title="Resume Tailor", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.make_service = make_service
    app.state.sessions = sessions or SessionStore(ttl_seconds=settings.api_session_ttl_minutes * 60)
    app.state.rate_limiter = RateLimiter(rate_limit if rate_limit is not None else settings.api_rate_limit_per_hour)
    app.state.max_upload_bytes = settings.api_max_upload_mb * 1024 * 1024
    app.include_router(router)

    @app.middleware("http")
    async def refresh_session_cookie(request: Request, call_next):
        """The server keeps a session while it's used, so the cookie's
        lifetime restarts on every request too."""
        response = await call_next(request)
        sid = request.cookies.get(SESSION_COOKIE)
        if sid and "set-cookie" not in response.headers and app.state.sessions.get(sid) is not None:
            response.set_cookie(SESSION_COOKIE, sid, httponly=True, samesite="lax",
                                max_age=app.state.sessions.ttl_seconds)
        return response
    if serve_web and os.path.isdir(WEB_DIST):
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
    return app


app = create_app()

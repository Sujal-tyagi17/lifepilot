"""Security middleware: hardening headers, CSP, and a lightweight rate limiter.

All local, no external services. The CSP intentionally restricts `connect-src`
to 'self', so the page can never send user data anywhere except this backend.
"""
from __future__ import annotations

import time
from collections import deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Content-Security-Policy.
# Every script, stylesheet, font and icon is served from this server, so
# scripts are 'self' only (no CDNs, no eval). 'unsafe-inline' for styles covers
# style attributes the UI sets (bar widths); it does not allow inline scripts.
_CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "font-src 'self'",
    "img-src 'self' data: blob: https://*.googleusercontent.com https://*.gravatar.com https://*.kinde.com",
    "connect-src 'self' https://*.kinde.com",
    "frame-src 'self' https://*.kinde.com",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self' https://*.kinde.com",
    "object-src 'none'",
])

_SECURITY_HEADERS = {
    "Content-Security-Policy": _CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer-when-downgrade",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin-allow-popups",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        for key, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        # The UI is plain ES modules with no build step, so their URLs never
        # change between versions. "no-cache" makes the browser revalidate each
        # file (a cheap 304 when unchanged) instead of mixing old cached modules
        # with new ones after an update, which leaves a blank page.
        path = request.url.path
        if path == "/" or path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory sliding-window limiter for /api/* endpoints (per client IP)."""

    def __init__(self, app, limit: int = 120, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            ip = request.client.host if request.client else "unknown"
            now = time.monotonic()
            with self._lock:
                dq = self._hits.setdefault(ip, deque())
                while dq and now - dq[0] > self.window:
                    dq.popleft()
                if len(dq) >= self.limit:
                    retry = int(self.window - (now - dq[0])) + 1
                    return JSONResponse(
                        {"detail": "Too many requests. Please slow down."},
                        status_code=429,
                        headers={"Retry-After": str(retry)},
                    )
                dq.append(now)
        return await call_next(request)


def add_security(app, *, rate_limit: int = 120, rate_window: int = 60) -> None:
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, limit=rate_limit, window_seconds=rate_window)

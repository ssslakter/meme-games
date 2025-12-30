"""Global rate limiting middleware."""
import re, time
from collections import defaultdict
from dataclasses import dataclass, field
from starlette.responses import Response

__all__ = ['RateLimitMiddleware', 'RateLimitState', 'get_client_ip']


def get_client_ip(scope: dict) -> str:
    """Extract client IP from ASGI scope, checking X-Forwarded-For first."""
    headers = dict(scope.get("headers", []))
    if forwarded := headers.get(b"x-forwarded-for", b"").decode():
        return forwarded.split(",")[0].strip()
    if client := scope.get("client"): return client[0]
    return "unknown"


@dataclass
class RateLimitState:
    """Tracks rate limit state for a single client."""
    requests: list[float] = field(default_factory=list)
    
    def clean(self, window: float):
        cutoff = time.monotonic() - window
        self.requests = [ts for ts in self.requests if ts > cutoff]
    
    def add(self): self.requests.append(time.monotonic())
    
    def is_limited(self, max_requests: int, window: float) -> bool:
        self.clean(window)
        return len(self.requests) >= max_requests


class RateLimitMiddleware:
    """Global rate limiting middleware. Default: 50 req/60s per IP."""
    
    def __init__(self, app, max_requests: int = 50, window: float = 60.0, skip_paths: list[str] = None):
        self.app = app
        self.max_requests = max_requests
        self.window = window
        self.skip_patterns = [re.compile(p) for p in (skip_paths or [])]
        self._state: dict[str, RateLimitState] = defaultdict(RateLimitState)
    
    def _should_skip(self, path: str) -> bool:
        return any(p.match(path) for p in self.skip_patterns)
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or self._should_skip(scope["path"]):
            return await self.app(scope, receive, send)
        
        state = self._state[get_client_ip(scope)]
        if state.is_limited(self.max_requests, self.window):
            resp = Response("Rate limit exceeded.", status_code=429,
                          headers={"Retry-After": str(int(self.window)), "X-RateLimit-Limit": str(self.max_requests)})
            return await resp(scope, receive, send)
        
        state.add()
        await self.app(scope, receive, send)

"""Rate limiting middleware for lobby/game creation endpoints."""
import re
from collections import defaultdict
from starlette.responses import Response
from .rate_limit import RateLimitState, get_client_ip

__all__ = ['LobbyCreationRateLimitMiddleware', 'LOBBY_PATTERNS']

# Default patterns for lobby creation routes - add new game patterns here
LOBBY_PATTERNS = [
    r"^/alias/[a-z0-9]+$",
    r"^/whoami/[a-z0-9]+$", 
    r"^/video/[a-z0-9]+$",
    r"^/codenames/[a-z0-9]+$",
]


class LobbyCreationRateLimitMiddleware:
    """Rate limiting for lobby creation. Default: 5 creations/60s per IP."""
    
    def __init__(self, app, max_creations: int = 5, window: float = 60.0, patterns: list[str] = None):
        self.app = app
        self.max_creations = max_creations
        self.window = window
        self.patterns = [re.compile(p, re.IGNORECASE) for p in (patterns or LOBBY_PATTERNS)]
        self._state: dict[str, RateLimitState] = defaultdict(RateLimitState)
    
    def _is_lobby_route(self, path: str, method: str) -> bool:
        return method.upper() == "GET" and any(p.match(path) for p in self.patterns)
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not self._is_lobby_route(scope["path"], scope.get("method", "GET")):
            return await self.app(scope, receive, send)
        
        state = self._state[get_client_ip(scope)]
        if state.is_limited(self.max_creations, self.window):
            resp = Response("Too many lobby requests. Please wait.", status_code=429,
                          headers={"Retry-After": str(int(self.window)), "X-RateLimit-Limit": str(self.max_creations)})
            return await resp(scope, receive, send)
        
        state.add()
        await self.app(scope, receive, send)

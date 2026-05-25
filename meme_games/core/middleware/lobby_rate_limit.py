import re
from .rate_limit import IpRateLimiter, _too_many

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
        self.window = window
        self.max_creations = max_creations
        self.patterns = [re.compile(p, re.IGNORECASE) for p in (patterns or LOBBY_PATTERNS)]
        self.limiter = IpRateLimiter(max_creations, window)

    def _is_lobby_route(self, path: str, method: str) -> bool:
        return method.upper() == "GET" and any(p.match(path) for p in self.patterns)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not self._is_lobby_route(scope["path"], scope.get("method", "GET")):
            return await self.app(scope, receive, send)
        if self.limiter.is_limited(scope):
            return await _too_many("Too many lobby requests. Please wait.", self.max_creations, self.window)(scope, receive, send)
        await self.app(scope, receive, send)

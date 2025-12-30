"""
Rate limiting middleware for Starlette/FastHTML applications.

Provides two levels of rate limiting:
1. Global rate limiting - limits all requests from an IP
2. Lobby creation rate limiting - stricter limits for lobby creation endpoints
"""
import time
import re
from collections import defaultdict
from dataclasses import dataclass, field
from starlette.requests import Request
from starlette.responses import Response

__all__ = ['RateLimitMiddleware', 'LobbyCreationRateLimitMiddleware']


@dataclass
class RateLimitState:
    """Tracks rate limit state for a single client."""
    requests: list[float] = field(default_factory=list)
    
    def clean_old_requests(self, window_seconds: float) -> None:
        """Remove requests older than the time window."""
        now = time.monotonic()
        cutoff = now - window_seconds
        self.requests = [ts for ts in self.requests if ts > cutoff]
    
    def add_request(self) -> None:
        """Record a new request."""
        self.requests.append(time.monotonic())
    
    def is_rate_limited(self, max_requests: int, window_seconds: float) -> bool:
        """Check if the client has exceeded the rate limit."""
        self.clean_old_requests(window_seconds)
        return len(self.requests) >= max_requests


class RateLimitMiddleware:
    """
    Global rate limiting middleware.
    
    Limits all IPs to a configurable number of requests per time window.
    Default: 50 requests per 60 seconds.
    """
    
    def __init__(
        self,
        app,
        max_requests: int = 50,
        window_seconds: float = 60.0,
        skip_paths: list[str] | None = None
    ):
        self.app = app
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.skip_patterns = [re.compile(p) for p in (skip_paths or [])]
        self._state: dict[str, RateLimitState] = defaultdict(RateLimitState)
    
    def _get_client_ip(self, scope: dict) -> str:
        """Extract client IP from request scope."""
        # Check for X-Forwarded-For header (for proxied requests)
        headers = dict(scope.get("headers", []))
        forwarded_for = headers.get(b"x-forwarded-for", b"").decode()
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        # Fall back to direct client IP
        client = scope.get("client")
        if client:
            return client[0]
        return "unknown"
    
    def _should_skip(self, path: str) -> bool:
        """Check if the path should be skipped from rate limiting."""
        return any(p.match(path) for p in self.skip_patterns)
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or self._should_skip(scope["path"]):
            await self.app(scope, receive, send)
            return
        
        client_ip = self._get_client_ip(scope)
        state = self._state[client_ip]
        
        if state.is_rate_limited(self.max_requests, self.window_seconds):
            response = Response(
                "Rate limit exceeded. Please try again later.",
                status_code=429,
                headers={
                    "Retry-After": str(int(self.window_seconds)),
                    "X-RateLimit-Limit": str(self.max_requests),
                }
            )
            await response(scope, receive, send)
            return
        
        state.add_request()
        await self.app(scope, receive, send)


class LobbyCreationRateLimitMiddleware:
    """
    Rate limiting middleware specifically for lobby creation endpoints.
    
    Applies stricter limits to prevent bots from creating too many lobbies.
    Default: 5 lobby creations per 60 seconds per IP.
    
    This middleware checks for specific path patterns that trigger lobby creation
    (e.g., /alias/{lobby_id}, /whoami/{lobby_id}, /video/{lobby_id}, /codenames/{lobby_id}).
    """
    
    # Patterns for lobby creation routes
    LOBBY_CREATION_PATTERNS = [
        r"^/alias/[a-z0-9]+$",
        r"^/whoami/[a-z0-9]+$", 
        r"^/video/[a-z0-9]+$",
        r"^/codenames/[a-z0-9]+$",
    ]
    
    def __init__(
        self,
        app,
        max_creations: int = 5,
        window_seconds: float = 60.0,
        lobby_patterns: list[str] | None = None
    ):
        self.app = app
        self.max_creations = max_creations
        self.window_seconds = window_seconds
        patterns = lobby_patterns or self.LOBBY_CREATION_PATTERNS
        self.lobby_patterns = [re.compile(p, re.IGNORECASE) for p in patterns]
        self._state: dict[str, RateLimitState] = defaultdict(RateLimitState)
    
    def _get_client_ip(self, scope: dict) -> str:
        """Extract client IP from request scope."""
        headers = dict(scope.get("headers", []))
        forwarded_for = headers.get(b"x-forwarded-for", b"").decode()
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        client = scope.get("client")
        if client:
            return client[0]
        return "unknown"
    
    def _is_lobby_creation_route(self, path: str, method: str) -> bool:
        """Check if this route could create a lobby (GET requests to lobby routes)."""
        # Only GET requests trigger lobby creation via get_or_create
        if method.upper() != "GET":
            return False
        return any(p.match(path) for p in self.lobby_patterns)
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        path = scope["path"]
        method = scope.get("method", "GET")
        
        if not self._is_lobby_creation_route(path, method):
            await self.app(scope, receive, send)
            return
        
        client_ip = self._get_client_ip(scope)
        state = self._state[client_ip]
        
        if state.is_rate_limited(self.max_creations, self.window_seconds):
            response = Response(
                "Too many lobby creation requests. Please wait before creating new lobbies.",
                status_code=429,
                headers={
                    "Retry-After": str(int(self.window_seconds)),
                    "X-RateLimit-Limit": str(self.max_creations),
                    "X-RateLimit-Type": "lobby-creation",
                }
            )
            await response(scope, receive, send)
            return
        
        # Note: We increment the counter for all potential lobby creation requests
        # Even if the lobby already exists, this prevents probing attacks
        state.add_request()
        await self.app(scope, receive, send)

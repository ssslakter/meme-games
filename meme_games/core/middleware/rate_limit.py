"""Global rate limiting middleware."""
import os, re, time
from collections import defaultdict
from dataclasses import dataclass, field
from starlette.responses import Response

__all__ = ['RateLimitMiddleware', 'RateLimitState', 'IpRateLimiter', 'get_client_ip', 'TRUSTED_PROXY_COUNT']

# Reverse proxies in front of the app. 0 (default) = reached directly, so trust only
# the socket address and ignore the spoofable X-Forwarded-For. Set to the proxy count
# (e.g. 1 behind nginx/Cloudflare) via the env var to read the right forwarded entry.
TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "0") or "0")


def get_client_ip(scope: dict, trusted_proxies: int | None = None) -> str:
    """Client IP from an ASGI scope, resistant to X-Forwarded-For spoofing.

    No trusted proxies -> the real socket peer (unforgeable). With N proxies -> the
    Nth-from-right X-Forwarded-For entry, ignoring left-hand entries a client injects."""
    n = TRUSTED_PROXY_COUNT if trusted_proxies is None else trusted_proxies
    client = scope.get("client")
    conn_ip = client[0] if client else "unknown"
    if n <= 0: return conn_ip
    headers = dict(scope.get("headers", []))
    parts = [p.strip() for p in headers.get(b"x-forwarded-for", b"").decode().split(",") if p.strip()]
    if not parts: return conn_ip
    idx = len(parts) - n
    return parts[idx] if 0 <= idx < len(parts) else parts[0]


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


class IpRateLimiter:
    """Per-IP sliding window. Self-prunes idle buckets so the map stays bounded."""

    def __init__(self, max_requests: int, window: float):
        self.max_requests, self.window = max_requests, window
        self._state: dict[str, RateLimitState] = defaultdict(RateLimitState)
        self._last_prune = time.monotonic()

    def _prune(self):
        now = time.monotonic()
        if now - self._last_prune < self.window: return
        self._last_prune = now
        for ip in list(self._state):
            self._state[ip].clean(self.window)
            if not self._state[ip].requests: del self._state[ip]

    def is_limited(self, scope) -> bool:
        """Record the request and return True if the client is over the limit."""
        self._prune()
        state = self._state[get_client_ip(scope)]
        if state.is_limited(self.max_requests, self.window): return True
        state.add()
        return False


def _too_many(msg: str, limit: int, window: float) -> Response:
    return Response(msg, status_code=429,
                    headers={"Retry-After": str(int(window)), "X-RateLimit-Limit": str(limit)})


class RateLimitMiddleware:
    """Global rate limiting middleware. Default: 50 req/60s per IP."""

    def __init__(self, app, max_requests: int = 50, window: float = 60.0, skip_paths: list[str] = None):
        self.app = app
        self.window = window
        self.max_requests = max_requests
        self.skip_patterns = [re.compile(p) for p in (skip_paths or [])]
        self.limiter = IpRateLimiter(max_requests, window)

    def _should_skip(self, path: str) -> bool:
        return any(p.match(path) for p in self.skip_patterns)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or self._should_skip(scope["path"]):
            return await self.app(scope, receive, send)
        if self.limiter.is_limited(scope):
            return await _too_many("Rate limit exceeded.", self.max_requests, self.window)(scope, receive, send)
        await self.app(scope, receive, send)

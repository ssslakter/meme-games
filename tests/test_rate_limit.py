"""Tests for rate limiting middleware."""
import asyncio, time
from meme_games.core.middleware.rate_limit import RateLimitState, RateLimitMiddleware, get_client_ip
from meme_games.core.middleware.lobby_rate_limit import LobbyCreationRateLimitMiddleware


class TestRateLimitState:
    """Tests for RateLimitState class."""
    
    def test_initial_state_is_empty(self):
        state = RateLimitState()
        assert len(state.requests) == 0
    
    def test_add(self):
        state = RateLimitState()
        state.add()
        assert len(state.requests) == 1
    
    def test_not_limited_under_max(self):
        state = RateLimitState()
        for _ in range(4):
            assert not state.is_limited(5, 60.0)
            state.add()
    
    def test_limited_at_max(self):
        state = RateLimitState()
        for _ in range(3): state.add()
        assert state.is_limited(3, 60.0)
    
    def test_requests_expire(self):
        state = RateLimitState()
        state.add(); state.add()
        assert state.is_limited(2, 0.1)
        time.sleep(0.15)
        assert not state.is_limited(2, 0.1)


class MockApp:
    """Mock ASGI app for testing middleware."""
    def __init__(self):
        self.call_count = 0
    
    async def __call__(self, scope, receive, send):
        self.call_count += 1
        await send({"type": "http.response.start", "status": 200, "headers": [[b"content-type", b"text/plain"]]})
        await send({"type": "http.response.body", "body": b"OK"})


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware class."""
    
    def test_client_ip_from_scope(self):
        assert get_client_ip({"client": ("192.168.1.1", 12345)}) == "192.168.1.1"
    
    def test_client_ip_from_x_forwarded_for(self):
        scope = {"client": ("127.0.0.1", 12345), "headers": [(b"x-forwarded-for", b"10.0.0.1, 192.168.1.1")]}
        assert get_client_ip(scope) == "10.0.0.1"
    
    def test_skip_paths(self):
        middleware = RateLimitMiddleware(MockApp(), skip_paths=[r"/static/.*"])
        assert middleware._should_skip("/static/css/style.css")
        assert not middleware._should_skip("/api/data")


class TestLobbyCreationRateLimitMiddleware:
    """Tests for LobbyCreationRateLimitMiddleware class."""
    
    def test_detects_lobby_routes(self):
        middleware = LobbyCreationRateLimitMiddleware(MockApp())
        assert middleware._is_lobby_route("/alias/abc12", "GET")
        assert middleware._is_lobby_route("/whoami/xyz99", "GET")
        assert middleware._is_lobby_route("/video/test1", "GET")
        assert middleware._is_lobby_route("/codenames/room1", "GET")
    
    def test_ignores_non_lobby_routes(self):
        middleware = LobbyCreationRateLimitMiddleware(MockApp())
        assert not middleware._is_lobby_route("/", "GET")
        assert not middleware._is_lobby_route("/alias", "GET")
        assert not middleware._is_lobby_route("/alias/abc12/settings", "GET")
    
    def test_ignores_non_get_methods(self):
        middleware = LobbyCreationRateLimitMiddleware(MockApp())
        assert not middleware._is_lobby_route("/alias/abc12", "POST")
        assert not middleware._is_lobby_route("/alias/abc12", "PUT")


def run_async(coro): return asyncio.new_event_loop().run_until_complete(coro)


class MockSend:
    def __init__(self): self.messages = []
    async def __call__(self, msg): self.messages.append(msg)


class MockReceive:
    async def __call__(self): return {"type": "http.request", "body": b""}


class TestRateLimitMiddlewareIntegration:
    """Integration tests for rate limit middleware."""
    
    def test_allows_requests_under_limit(self):
        app = MockApp()
        middleware = RateLimitMiddleware(app, max_requests=5, window=60.0)
        scope = {"type": "http", "path": "/api/test", "client": ("192.168.1.1", 12345)}
        for _ in range(4): run_async(middleware(scope, MockReceive(), MockSend()))
        assert app.call_count == 4
    
    def test_blocks_requests_over_limit(self):
        app = MockApp()
        middleware = RateLimitMiddleware(app, max_requests=2, window=60.0)
        scope = {"type": "http", "path": "/api/test", "client": ("192.168.1.1", 12345)}
        for _ in range(2): run_async(middleware(scope, MockReceive(), MockSend()))
        assert app.call_count == 2
        send = MockSend()
        run_async(middleware(scope, MockReceive(), send))
        assert app.call_count == 2
        assert send.messages[0]["status"] == 429


class TestLobbyCreationRateLimitMiddlewareIntegration:
    """Integration tests for lobby creation rate limit middleware."""
    
    def test_limits_lobby_requests(self):
        app = MockApp()
        middleware = LobbyCreationRateLimitMiddleware(app, max_creations=2, window=60.0)
        scope = {"type": "http", "path": "/alias/test1", "method": "GET", "client": ("192.168.1.1", 12345)}
        for _ in range(2): run_async(middleware(scope, MockReceive(), MockSend()))
        assert app.call_count == 2
        send = MockSend()
        run_async(middleware(scope, MockReceive(), send))
        assert app.call_count == 2
        assert send.messages[0]["status"] == 429
    
    def test_allows_non_lobby_routes(self):
        app = MockApp()
        middleware = LobbyCreationRateLimitMiddleware(app, max_creations=1, window=60.0)
        lobby_scope = {"type": "http", "path": "/alias/test1", "method": "GET", "client": ("192.168.1.1", 12345)}
        run_async(middleware(lobby_scope, MockReceive(), MockSend()))
        other_scope = {"type": "http", "path": "/", "method": "GET", "client": ("192.168.1.1", 12345)}
        for _ in range(10): run_async(middleware(other_scope, MockReceive(), MockSend()))
        assert app.call_count == 11


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

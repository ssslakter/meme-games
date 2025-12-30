"""
Tests for rate limiting middleware.
"""
import asyncio
import time
from meme_games.core.rate_limit import (
    RateLimitState, 
    RateLimitMiddleware, 
    LobbyCreationRateLimitMiddleware,
    get_client_ip
)


class TestRateLimitState:
    """Tests for RateLimitState class."""
    
    def test_initial_state_is_empty(self):
        state = RateLimitState()
        assert len(state.requests) == 0
    
    def test_add_request(self):
        state = RateLimitState()
        state.add_request()
        assert len(state.requests) == 1
    
    def test_not_rate_limited_under_max(self):
        state = RateLimitState()
        max_requests = 5
        window_seconds = 60.0
        
        for _ in range(4):
            assert not state.is_rate_limited(max_requests, window_seconds)
            state.add_request()
    
    def test_rate_limited_at_max(self):
        state = RateLimitState()
        max_requests = 3
        window_seconds = 60.0
        
        for _ in range(3):
            state.add_request()
        
        assert state.is_rate_limited(max_requests, window_seconds)
    
    def test_requests_expire_after_window(self):
        state = RateLimitState()
        max_requests = 2
        window_seconds = 0.1  # Very short window for testing
        
        state.add_request()
        state.add_request()
        assert state.is_rate_limited(max_requests, window_seconds)
        
        time.sleep(0.15)
        assert not state.is_rate_limited(max_requests, window_seconds)


class MockApp:
    """Mock ASGI app for testing middleware."""
    def __init__(self):
        self.called = False
        self.call_count = 0
    
    async def __call__(self, scope, receive, send):
        self.called = True
        self.call_count += 1
        # Send a simple 200 response
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"text/plain"]],
        })
        await send({
            "type": "http.response.body",
            "body": b"OK",
        })


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware class."""
    
    def test_extracts_client_ip_from_scope(self):
        scope = {"client": ("192.168.1.1", 12345)}
        
        ip = get_client_ip(scope)
        assert ip == "192.168.1.1"
    
    def test_extracts_client_ip_from_x_forwarded_for(self):
        scope = {
            "client": ("127.0.0.1", 12345),
            "headers": [(b"x-forwarded-for", b"10.0.0.1, 192.168.1.1")]
        }
        
        ip = get_client_ip(scope)
        assert ip == "10.0.0.1"
    
    def test_skip_paths(self):
        middleware = RateLimitMiddleware(MockApp(), skip_paths=[r"/static/.*"])
        
        assert middleware._should_skip("/static/css/style.css")
        assert not middleware._should_skip("/api/data")


class TestLobbyCreationRateLimitMiddleware:
    """Tests for LobbyCreationRateLimitMiddleware class."""
    
    def test_detects_lobby_creation_routes(self):
        middleware = LobbyCreationRateLimitMiddleware(MockApp())
        
        # These should match (GET requests to lobby routes)
        assert middleware._is_lobby_creation_route("/alias/abc12", "GET")
        assert middleware._is_lobby_creation_route("/whoami/xyz99", "GET")
        assert middleware._is_lobby_creation_route("/video/test1", "GET")
        assert middleware._is_lobby_creation_route("/codenames/room1", "GET")
    
    def test_ignores_non_lobby_routes(self):
        middleware = LobbyCreationRateLimitMiddleware(MockApp())
        
        assert not middleware._is_lobby_creation_route("/", "GET")
        assert not middleware._is_lobby_creation_route("/alias", "GET")
        assert not middleware._is_lobby_creation_route("/alias/abc12/settings", "GET")
    
    def test_ignores_non_get_methods(self):
        middleware = LobbyCreationRateLimitMiddleware(MockApp())
        
        # POST requests shouldn't trigger lobby creation limit
        assert not middleware._is_lobby_creation_route("/alias/abc12", "POST")
        assert not middleware._is_lobby_creation_route("/alias/abc12", "PUT")


def run_async(coro):
    """Helper to run async code in tests."""
    return asyncio.new_event_loop().run_until_complete(coro)


class MockSend:
    """Mock send function for testing ASGI middleware."""
    def __init__(self):
        self.messages = []
    
    async def __call__(self, message):
        self.messages.append(message)


class MockReceive:
    """Mock receive function for testing ASGI middleware."""
    async def __call__(self):
        return {"type": "http.request", "body": b""}


class TestRateLimitMiddlewareIntegration:
    """Integration tests for rate limit middleware."""
    
    def test_allows_requests_under_limit(self):
        app = MockApp()
        middleware = RateLimitMiddleware(app, max_requests=5, window_seconds=60.0)
        
        scope = {"type": "http", "path": "/api/test", "client": ("192.168.1.1", 12345)}
        
        for _ in range(4):
            send = MockSend()
            run_async(middleware(scope, MockReceive(), send))
        
        assert app.call_count == 4
    
    def test_blocks_requests_over_limit(self):
        app = MockApp()
        middleware = RateLimitMiddleware(app, max_requests=2, window_seconds=60.0)
        
        scope = {"type": "http", "path": "/api/test", "client": ("192.168.1.1", 12345)}
        
        # First 2 requests should pass
        for _ in range(2):
            send = MockSend()
            run_async(middleware(scope, MockReceive(), send))
        
        assert app.call_count == 2
        
        # 3rd request should be blocked
        send = MockSend()
        run_async(middleware(scope, MockReceive(), send))
        
        # Check that we got a 429 response
        assert app.call_count == 2  # App wasn't called again
        response_start = send.messages[0]
        assert response_start["status"] == 429


class TestLobbyCreationRateLimitMiddlewareIntegration:
    """Integration tests for lobby creation rate limit middleware."""
    
    def test_limits_lobby_creation_requests(self):
        app = MockApp()
        middleware = LobbyCreationRateLimitMiddleware(app, max_creations=2, window_seconds=60.0)
        
        scope = {
            "type": "http", 
            "path": "/alias/test1", 
            "method": "GET",
            "client": ("192.168.1.1", 12345)
        }
        
        # First 2 requests should pass
        for _ in range(2):
            send = MockSend()
            run_async(middleware(scope, MockReceive(), send))
        
        assert app.call_count == 2
        
        # 3rd lobby creation request should be blocked
        send = MockSend()
        run_async(middleware(scope, MockReceive(), send))
        
        assert app.call_count == 2  # App wasn't called again
        response_start = send.messages[0]
        assert response_start["status"] == 429
    
    def test_allows_non_lobby_routes(self):
        app = MockApp()
        middleware = LobbyCreationRateLimitMiddleware(app, max_creations=1, window_seconds=60.0)
        
        # First hit the limit with a lobby creation
        lobby_scope = {
            "type": "http", 
            "path": "/alias/test1", 
            "method": "GET",
            "client": ("192.168.1.1", 12345)
        }
        run_async(middleware(lobby_scope, MockReceive(), MockSend()))
        
        # Non-lobby routes should still be allowed
        other_scope = {
            "type": "http", 
            "path": "/", 
            "method": "GET",
            "client": ("192.168.1.1", 12345)
        }
        
        for _ in range(10):
            run_async(middleware(other_scope, MockReceive(), MockSend()))
        
        assert app.call_count == 11  # 1 lobby + 10 other routes


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

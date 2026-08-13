"""Tests for the crawler/unfurler filter. Rate limiting is nginx + crowdsec's job."""
import asyncio
from meme_games.core.middleware.bot_filter import BotFilterMiddleware


class MockApp:
    """Mock ASGI app for testing middleware."""
    def __init__(self):
        self.call_count = 0

    async def __call__(self, scope, receive, send):
        self.call_count += 1
        await send({"type": "http.response.start", "status": 200, "headers": [[b"content-type", b"text/plain"]]})
        await send({"type": "http.response.body", "body": b"OK"})


def run_async(coro): return asyncio.new_event_loop().run_until_complete(coro)


class MockSend:
    def __init__(self): self.messages = []
    async def __call__(self, msg): self.messages.append(msg)


class MockReceive:
    async def __call__(self): return {"type": "http.request", "body": b""}


class TestBotFilterMiddleware:
    """Tests for crawler/unfurler filtering."""

    def _scope(self, path, ua=b"", method="GET"):
        return {"type": "http", "path": path, "method": method, "client": ("1.2.3.4", 1),
                "headers": [(b"user-agent", ua)]}

    def test_serves_robots_txt(self):
        app = MockApp(); send = MockSend()
        run_async(BotFilterMiddleware(app)(self._scope("/robots.txt"), MockReceive(), send))
        assert app.call_count == 0
        assert send.messages[0]["status"] == 200
        assert b"Disallow" in send.messages[1]["body"]

    def test_bot_ua_on_lobby_route_gets_preview(self):
        app = MockApp(); send = MockSend()
        run_async(BotFilterMiddleware(app)(self._scope("/alias/test1", b"Discordbot/2.0"), MockReceive(), send))
        assert app.call_count == 0  # no lobby created
        assert b"og:title" in send.messages[1]["body"]

    def test_human_ua_passes_through(self):
        app = MockApp()
        run_async(BotFilterMiddleware(app)(self._scope("/alias/test1", b"Mozilla/5.0 (X11) Firefox/123"), MockReceive(), MockSend()))
        assert app.call_count == 1

    def test_bot_ua_on_non_lobby_route_passes_through(self):
        app = MockApp()
        run_async(BotFilterMiddleware(app)(self._scope("/", b"Discordbot/2.0"), MockReceive(), MockSend()))
        assert app.call_count == 1

    def test_detects_lobby_routes(self):
        mw = BotFilterMiddleware(MockApp())
        assert mw._is_lobby_route("/alias/abc12", "GET")
        assert mw._is_lobby_route("/whoami/xyz99", "GET")
        assert mw._is_lobby_route("/video/test1", "GET")
        assert mw._is_lobby_route("/codenames/room1", "GET")
        assert not mw._is_lobby_route("/", "GET")
        assert not mw._is_lobby_route("/alias", "GET")
        assert not mw._is_lobby_route("/alias/abc12/settings", "GET")
        assert not mw._is_lobby_route("/alias/abc12", "POST")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

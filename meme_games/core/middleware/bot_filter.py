"""Stops crawlers/link-unfurlers from creating phantom lobbies, and serves robots.txt."""
import re
from starlette.responses import Response
from fasthtml.common import Html, Head, Body, Title, Meta, to_xml
from .lobby_rate_limit import LOBBY_PATTERNS

__all__ = ['BotFilterMiddleware', 'BOT_UA_PATTERN']

# Crawlers, search engines, chat-app unfurlers and scripted clients. They hit shared
# lobby URLs and would otherwise create lobbies nobody joins, filling the limit.
BOT_UA_PATTERN = re.compile(
    r"bot|crawl|spider|slurp|preview|scrape|embed|fetch|"
    r"facebookexternalhit|whatsapp|vkshare|skype|"
    r"python-requests|curl|wget|go-http|okhttp|java/|httpx", re.IGNORECASE)

ROBOTS_TXT = "User-agent: *\nDisallow: /\n"
# Minimal page so shared links still unfurl, without reaching the app (no lobby created).
PREVIEW_HTML = to_xml(Html(
    Head(
        Meta(charset="utf-8"),
        Title("Meme Games"),
        Meta(name="robots", content="noindex, nofollow"),
        Meta(property="og:title", content="Meme Games"),
        Meta(property="og:description", content="Random social games to play with friends")),
    Body("Open this link in your browser to play.")))


class BotFilterMiddleware:
    """Serves robots.txt and answers bot UAs with a preview instead of creating a lobby."""

    def __init__(self, app, patterns: list[str] = None):
        self.app = app
        self.patterns = [re.compile(p, re.IGNORECASE) for p in (patterns or LOBBY_PATTERNS)]

    def _ua(self, scope) -> str:
        return dict(scope.get("headers", [])).get(b"user-agent", b"").decode(errors="ignore")

    def _is_lobby_route(self, path: str, method: str) -> bool:
        return method.upper() == "GET" and any(p.match(path) for p in self.patterns)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            if scope["path"] == "/robots.txt":
                return await Response(ROBOTS_TXT, media_type="text/plain")(scope, receive, send)
            if self._is_lobby_route(scope["path"], scope.get("method", "GET")) and BOT_UA_PATTERN.search(self._ua(scope)):
                return await Response(PREVIEW_HTML, media_type="text/html")(scope, receive, send)
        await self.app(scope, receive, send)

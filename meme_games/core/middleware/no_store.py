"""Keeps the browser from replaying a stale page on Back.

Every HTML page here is rendered for one user, in one lobby, at one moment. When the
browser answers a Back navigation from its own cache it resurrects a snapshot the
server has already moved past - a nickname prompt for someone who has since been
named, a board missing whoever joined after, settings that were changed since.
Static files set their own Cache-Control and keep it.
"""
from starlette.datastructures import MutableHeaders

__all__ = ['NoStoreHTMLMiddleware']


class NoStoreHTMLMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http': return await self.app(scope, receive, send)

        async def send_no_store(message):
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(scope=message)
                if headers.get('content-type', '').startswith('text/html') and 'cache-control' not in headers:
                    headers['cache-control'] = 'no-store'
            await send(message)

        await self.app(scope, receive, send_no_store)

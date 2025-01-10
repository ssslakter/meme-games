import re
from starlette.middleware.sessions import SessionMiddleware

class ConditionalSessionMiddleware:
    def __init__(self, app, skip: list[str]=None, **kwargs):
        self.app = app
        self.session_middleware = SessionMiddleware(app, **kwargs)
        self.skip_paths = [re.compile(p) for p in skip or []]

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and any(p.match(scope["path"]) for p in self.skip_paths):
            # Skip the SessionMiddleware for exempt paths
            await self.app(scope, receive, send)
        else:
            # Use the SessionMiddleware for all other paths
            await self.session_middleware(scope, receive, send)

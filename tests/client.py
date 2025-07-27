from anyio import from_thread
from functools import partial
from httpx import AsyncClient, Response
import websockets

class TestWebClient:
    "A simple httpx client that doesn't require `async` and supports websockets"
    def __init__(self, url="http://testserver"):
        self.base_url = url
        self._portal_cm = None
        self.portal = None
        self.cli = None
        self.ws = None

    def __enter__(self):
        self._portal_cm = from_thread.start_blocking_portal()
        self.portal = self._portal_cm.__enter__()
        self.cli = self.portal.call(partial(AsyncClient, base_url=self.base_url))
        return self

    async def _aclose(self):
        if self.ws:
            await self.ws.close()
        if self.cli:
            await self.cli.aclose()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.portal:
            self.portal.call(self._aclose)
        
        if self._portal_cm:
            self._portal_cm.__exit__(exc_type, exc_val, exc_tb)

    def _sync(self, method, url, **kwargs):
        async def _request():
            return await self.cli.request(method, url, **kwargs)
        return self.portal.call(_request)

    def get(self, url, **kwargs) -> Response:
        return self._sync("get", url, **kwargs)
    
    def post(self, url, **kwargs) -> Response:
        return self._sync("post", url, **kwargs)
    
    def delete(self, url, **kwargs) -> Response:
        return self._sync("delete", url, **kwargs)
    
    def put(self, url, **kwargs) -> Response:
        return self._sync("put", url, **kwargs)
    
    def patch(self, url, **kwargs) -> Response:
        return self._sync("patch", url, **kwargs)
    
    def options(self, url, **kwargs) -> Response:
        return self._sync("options", url, **kwargs)

    def connect_ws(self, ws_url):
        headers = [
            ('Cookie', "; ".join(f"{name}={value}" for name, value in self.cli.cookies.items())),
            ('User-Agent', self.cli.headers.get('User-Agent', 'TestWebClient')),
        ]
        async def _connect(): self.ws = await websockets.connect(ws_url, additional_headers=headers)
        self.portal.call(_connect)
    
    def send_ws(self, msg):
        """Send a text message through WebSocket."""
        async def _request():
            return await self.ws.send(msg)
        return self.portal.call(_request)

    def recv_ws(self):
        """Receive a text message from WebSocket."""
        async def _recv():
            return await self.ws.recv()
        return self.portal.call(_recv)

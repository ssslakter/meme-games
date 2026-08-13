import json
from dataclasses import dataclass

import httpx


class GameAPIError(RuntimeError):
    def __init__(self, response: httpx.Response):
        try: message = response.json().get('detail') or response.json().get('message')
        except ValueError: message = response.text
        super().__init__(message or f'Game API returned {response.status_code}')
        self.status_code = response.status_code


@dataclass(frozen=True)
class Settings:
    app_url: str
    gateway_secret: str
    allowed_hosts: tuple[str, ...]
    allowed_origins: tuple[str, ...]


class GameClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.http = httpx.AsyncClient(base_url=settings.app_url.rstrip('/'), timeout=15)

    def _headers(self, token=None):
        headers = {'X-Meme-Games-Gateway': self.settings.gateway_secret}
        if token: headers['Authorization'] = f'Bearer {token}'
        return headers

    async def close(self): await self.http.aclose()

    async def _agent_get(self, path: str, token: str):
        response = await self.http.get(path, headers=self._headers(token))
        if response.is_error: raise GameAPIError(response)
        return response.json()

    async def identity(self, token: str): return await self._agent_get('/identity', token)
    async def state(self, token: str): return await self._agent_get('/state', token)

    async def action(self, token: str, action: str, arguments=None):
        response = await self.http.post('/action', headers=self._headers(token),
                                        json={'action': action, 'arguments': arguments or {}})
        if response.status_code not in (200, 409): raise GameAPIError(response)
        return response.json()

    async def presence(self, token: str, connected: bool):
        response = await self.http.post('/presence', headers=self._headers(token), json={'connected': connected})
        if response.is_error: raise GameAPIError(response)

    async def events(self):
        """Reconnect forever; events are invalidations so no replay cursor is needed."""
        while True:
            try:
                async with self.http.stream('GET', '/events', headers=self._headers(), timeout=None) as response:
                    if response.is_error: raise GameAPIError(response)
                    async for line in response.aiter_lines():
                        if line.startswith('data: '): yield json.loads(line[6:])
            except (httpx.TransportError, GameAPIError):
                import asyncio
                await asyncio.sleep(1)

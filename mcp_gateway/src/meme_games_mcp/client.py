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
    auth_token: str
    allowed_hosts: tuple[str, ...]
    allowed_origins: tuple[str, ...]


class GameClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.http = httpx.AsyncClient(base_url=settings.app_url.rstrip('/'), timeout=15)

    def _headers(self): return {'X-Meme-Games-Gateway': self.settings.gateway_secret}

    async def close(self): await self.http.aclose()

    async def _post(self, path: str, data: dict, timeout=None):
        response = await self.http.post(path, headers=self._headers(), json=data, timeout=timeout)
        if response.is_error: raise GameAPIError(response)
        return response.json()

    async def join(self, lobby_code: str, name: str):
        return await self._post('/join', {'lobby_code': lobby_code, 'name': name})

    async def rules(self, game: str):
        return await self._post('/rules', {'game': game})

    async def state(self, player_session: str, full: bool = False):
        return await self._post('/state', {'player_session': player_session, 'full': full})

    async def action(self, player_session: str, action: str, arguments=None):
        response = await self.http.post('/action', headers=self._headers(), json={
            'player_session': player_session, 'action': action, 'arguments': arguments or {}})
        if response.status_code not in (200, 409): raise GameAPIError(response)
        return response.json()

    async def wait_events(self, player_session: str, cursor: int, timeout_seconds: int):
        return await self._post('/events', {'player_session': player_session, 'cursor': cursor,
                                             'timeout_seconds': timeout_seconds}, timeout=timeout_seconds + 5)

    async def leave(self, player_session: str):
        return await self._post('/leave', {'player_session': player_session})

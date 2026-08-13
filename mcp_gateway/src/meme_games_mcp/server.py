import asyncio
import contextvars
import json
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server import MCPServer
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.server.subscriptions import InMemorySubscriptionBus, ResourceUpdated
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from mcp_types import INVALID_REQUEST, SubscriptionsListenRequestParams
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Mount

from .client import GameAPIError, GameClient, Settings


current_token = contextvars.ContextVar('agent_token', default=None)


@dataclass
class ToolResult:
    ok: bool
    message: str
    revision: int


class KnownAgents:
    def __init__(self): self.by_lobby = defaultdict(dict)

    def remember(self, identity: dict, token: str):
        self.by_lobby[identity['lobby_id']][identity['resource_uri']] = token

    def forget(self, lobby_id: str, uri: str):
        self.by_lobby[lobby_id].pop(uri, None)


def bearer_token() -> str:
    token = current_token.get()
    if not token: raise MCPError(INVALID_REQUEST, 'Missing agent credential')
    return token


class BearerMiddleware:
    def __init__(self, app): self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http': return await self.app(scope, receive, send)
        headers = {key.lower(): value for key, value in scope['headers']}
        scheme, _, token = headers.get(b'authorization', b'').decode().partition(' ')
        if scheme.lower() != 'bearer' or not token:
            return await PlainTextResponse('Missing agent credential', 401)(scope, receive, send)
        context_token = current_token.set(token)
        try: await self.app(scope, receive, send)
        finally: current_token.reset(context_token)


def build_gateway(settings: Settings, client=None):
    client, known, bus = client or GameClient(settings), KnownAgents(), InMemorySubscriptionBus()

    async def identify(token: str):
        identity = await client.identity(token)
        known.remember(identity, token)
        return identity

    async def gate_subscriptions(ctx: ServerRequestContext, call_next: CallNext) -> HandlerResult:
        if ctx.method == 'subscriptions/listen':
            token = bearer_token()
            params = SubscriptionsListenRequestParams.model_validate(ctx.params or {}, by_name=False)
            identity = await identify(token)
            allowed = identity['resource_uri']
            requested = params.notifications.resource_subscriptions or ()
            if any(uri != allowed for uri in requested):
                raise MCPError(INVALID_REQUEST, 'Not permitted to watch the requested resource')
            await client.presence(token, True)
            try: return await call_next(ctx)
            finally: await client.presence(token, False)
        return await call_next(ctx)

    mcp = MCPServer('Meme Games', subscriptions=bus, middleware=[gate_subscriptions],
                    instructions='Play social games as an invited agent. Read your state after every update.')

    @mcp.resource('game://lobbies/{lobby_id}/agents/{agent_id}/state')
    async def game_state(lobby_id: str, agent_id: str) -> str:
        token = bearer_token()
        identity = await identify(token)
        if identity['lobby_id'] != lobby_id or identity['agent_id'] != agent_id:
            raise MCPError(INVALID_REQUEST, 'Unknown game resource')
        return json.dumps(await client.state(token))

    async def act(name: str, arguments=None):
        token = bearer_token()
        await identify(token)
        return ToolResult(**await client.action(token, name, arguments))

    @mcp.tool()
    async def join_team(team: str) -> ToolResult:
        """Join the red or blue Codenames team. Legal while the lobby is waiting."""
        return await act('join_team', {'team': team})

    @mcp.tool()
    async def set_role(role: str) -> ToolResult:
        """Choose operative or spymaster after joining a Codenames team."""
        return await act('set_role', {'role': role})

    @mcp.tool()
    async def give_clue(clue: str, number: int) -> ToolResult:
        """As the active spymaster, give a one-word clue and its target count."""
        return await act('give_clue', {'clue': clue, 'number': number})

    @mcp.tool()
    async def reveal_card(card_id: str) -> ToolResult:
        """As an active operative, reveal an unrevealed card by its state ID."""
        return await act('reveal_card', {'card_id': card_id})

    @mcp.tool()
    async def end_turn() -> ToolResult:
        """End your team's current guessing turn."""
        return await act('end_turn')

    @mcp.tool()
    async def spectate() -> ToolResult:
        """Leave your team and return to spectators while the lobby is unlocked."""
        return await act('spectate')

    async def forward_events():
        async for event in client.events():
            for uri, token in list(known.by_lobby[event['lobby_id']].items()):
                try: await client.state(token)
                except GameAPIError:
                    known.forget(event['lobby_id'], uri)
                    continue
                await bus.publish(ResourceUpdated(uri=uri))

    security = TransportSecuritySettings(
        allowed_hosts=list(settings.allowed_hosts), allowed_origins=list(settings.allowed_origins))
    mcp_app = mcp.streamable_http_app(transport_security=security)

    @asynccontextmanager
    async def lifespan(_app):
        async with mcp.session_manager.run():
            task = asyncio.create_task(forward_events())
            try: yield
            finally:
                task.cancel()
                await client.close()

    app = Starlette(routes=[Mount('/', app=mcp_app)], lifespan=lifespan)
    return BearerMiddleware(app), mcp, client, known, bus

import hmac
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Literal

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Mount

from .client import GameClient, Settings


@dataclass
class ToolResult:
    ok: bool
    message: str
    revision: int
    hint: str = 'Read game state before taking another action.'


@dataclass
class JoinResult:
    player_session: str
    lobby_id: str
    name: str
    cursor: int


@dataclass
class EventResult:
    events: list[dict]
    next_cursor: int
    hint: str


class BearerMiddleware:
    def __init__(self, app, auth_token: str): self.app, self.auth_token = app, auth_token

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http': return await self.app(scope, receive, send)
        headers = {key.lower(): value for key, value in scope['headers']}
        scheme, _, token = headers.get(b'authorization', b'').decode().partition(' ')
        if scheme.lower() != 'bearer' or not hmac.compare_digest(token, self.auth_token):
            return await PlainTextResponse('Invalid MCP credential', 401)(scope, receive, send)
        await self.app(scope, receive, send)


def build_gateway(settings: Settings, client=None):
    client = client or GameClient(settings)
    mcp = MCPServer('Meme Games', instructions=(
        'Join an existing lobby to receive a private player_session. Keep that handle secret and pass it '
        'to every state, event, leave, and game-action tool. Read state before acting.'))

    @mcp.tool()
    async def join_lobby(lobby_code: str, name: str) -> JoinResult:
        """Join an agent-enabled existing lobby as a new spectator with a unique name."""
        return JoinResult(**await client.join(lobby_code, name))

    @mcp.tool()
    async def get_game_state(player_session: str) -> dict:
        """Read receiver-specific game state and currently available actions."""
        return await client.state(player_session)

    @mcp.tool()
    async def wait_for_events(player_session: str, cursor: int, timeout_seconds: int = 25) -> EventResult:
        """Wait up to 25 seconds for changes. Reuse next_cursor on the next call."""
        return EventResult(**await client.wait_events(
            player_session, cursor, min(max(timeout_seconds, 1), 25)))

    @mcp.tool()
    async def leave_lobby(player_session: str) -> ToolResult:
        """Close this player session and remove its player from the lobby."""
        return ToolResult(**await client.leave(player_session))

    async def act(player_session: str, name: str, arguments=None):
        return ToolResult(**await client.action(player_session, name, arguments))

    @mcp.tool()
    async def codenames_join_team(player_session: str, team: str) -> ToolResult:
        """Join the red or blue Codenames team while the lobby is waiting."""
        return await act(player_session, 'codenames_join_team', {'team': team})

    @mcp.tool()
    async def codenames_set_role(player_session: str, role: str) -> ToolResult:
        """Choose operative or spymaster after joining a Codenames team."""
        return await act(player_session, 'codenames_set_role', {'role': role})

    @mcp.tool()
    async def codenames_give_clue(player_session: str, clue: str, number: int) -> ToolResult:
        """As the active Codenames spymaster, give a one-word clue and target count."""
        return await act(player_session, 'codenames_give_clue', {'clue': clue, 'number': number})

    @mcp.tool()
    async def codenames_reveal_card(player_session: str, card_id: str) -> ToolResult:
        """As an active Codenames operative, reveal an unrevealed card by ID."""
        return await act(player_session, 'codenames_reveal_card', {'card_id': card_id})

    @mcp.tool()
    async def codenames_end_turn(player_session: str) -> ToolResult:
        """End your Codenames team's guessing turn."""
        return await act(player_session, 'codenames_end_turn')

    @mcp.tool()
    async def codenames_spectate(player_session: str) -> ToolResult:
        """Leave your current game seat and become a spectator when legal."""
        return await act(player_session, 'codenames_spectate')

    @mcp.tool()
    async def whoami_write_card(player_session: str, text: str) -> ToolResult:
        """Write or revise the hidden identity card for your next Who Am I player."""
        return await act(player_session, 'whoami_write_card', {'text': text})

    @mcp.tool()
    async def whoami_ask_question(player_session: str, question: str) -> ToolResult:
        """Ask a yes/no question when it is your Who Am I turn."""
        return await act(player_session, 'whoami_ask_question', {'question': question})

    @mcp.tool()
    async def whoami_answer_question(
            player_session: str, answer: Literal['yes', 'no', 'not_sure']) -> ToolResult:
        """Answer the current Who Am I question with yes, no, or not_sure."""
        return await act(player_session, 'whoami_answer_question', {'answer': answer})

    @mcp.tool()
    async def whoami_write_note(player_session: str, text: str) -> ToolResult:
        """Replace your own Who Am I deduction notes."""
        return await act(player_session, 'whoami_write_note', {'text': text})

    @mcp.tool()
    async def whoami_end_turn(player_session: str) -> ToolResult:
        """End your Who Am I turn and advance to the next player."""
        return await act(player_session, 'whoami_end_turn')

    security = TransportSecuritySettings(
        allowed_hosts=list(settings.allowed_hosts), allowed_origins=list(settings.allowed_origins))
    mcp_app = mcp.streamable_http_app(transport_security=security)

    @asynccontextmanager
    async def lifespan(_app):
        async with mcp.session_manager.run():
            try: yield
            finally: await client.close()

    app = Starlette(routes=[Mount('/', app=mcp_app)], lifespan=lifespan)
    return BearerMiddleware(app, settings.auth_token), mcp, client

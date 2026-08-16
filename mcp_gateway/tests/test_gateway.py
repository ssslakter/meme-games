import json
import pytest
from mcp import Client

from meme_games_mcp.client import Settings
from meme_games_mcp.server import BearerMiddleware, build_gateway


HANDLE = 'mgps_player_one'


class FakeGameClient:
    def __init__(self): self.actions = []

    async def join(self, lobby_code, name):
        return {'player_session': HANDLE, 'lobby_id': lobby_code, 'name': name, 'cursor': 3}

    async def rules(self, game):
        return {'game': game, 'rules': f'# {game}\nrules text'}

    async def state(self, player_session, full=False):
        assert player_session == HANDLE
        return {'full': full, 'revision': 3, 'phase': 'waiting', 'you': {'id': 'p1'},
                'available_actions': ['codenames_join_team'],
                'state': {'lobby_id': 'room'} if full else None,
                'changes': {} if full else {'turn': 'red'}}

    async def action(self, player_session, action, arguments=None):
        assert player_session == HANDLE
        self.actions.append((action, arguments or {}))
        return {'ok': True, 'message': action, 'revision': 4}

    async def wait_events(self, player_session, cursor, timeout_seconds):
        assert player_session == HANDLE
        return {'events': [{'sequence': 4, 'revision': 4,
                            'topics': ['turn'], 'happened': ['the turn moved on']}],
                'next_cursor': 4}

    async def leave(self, player_session):
        assert player_session == HANDLE
        return {'ok': True, 'message': 'Left lobby', 'revision': 5}

    async def close(self): pass


@pytest.mark.asyncio
async def test_tools_use_independent_player_session_arguments():
    fake = FakeGameClient()
    settings = Settings('http://app', 'private', 'public', ('testserver',), ())
    _, mcp, _ = build_gateway(settings, fake)
    async with Client(mcp) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools.tools} >= {
            'join_lobby', 'get_game_state', 'leave_lobby', 'codenames_join_team',
            'codenames_set_role', 'codenames_give_clue', 'codenames_reveal_card',
            'codenames_end_turn', 'codenames_spectate', 'wait_for_events',
            'whoami_write_card', 'whoami_ask_question', 'whoami_answer_question',
            'whoami_end_turn', 'get_game_rules'}
        # notes are a human aid; an agent already holds the whole history in context
        assert not {'join_team', 'set_role', 'give_clue', 'reveal_card', 'end_turn', 'spectate',
                    'whoami_write_note'} & {tool.name for tool in tools.tools}
        joined = await client.call_tool('join_lobby', {'lobby_code': 'room', 'name': 'Robot'})
        assert joined.structured_content['player_session'] == HANDLE
        state = await client.call_tool('get_game_state', {'player_session': HANDLE})
        # the tool declares its output shape, so the result comes back structured
        assert state.structured_content['revision'] == 3
        assert state.structured_content['available_actions'] == ['codenames_join_team']
        result = await client.call_tool('codenames_join_team', {'player_session': HANDLE, 'team': 'red'})
        assert result.structured_content['ok']
        events = await client.call_tool('wait_for_events', {'player_session': HANDLE, 'cursor': 3})
        assert events.structured_content['next_cursor'] == 4
        rules = await client.call_tool('get_game_rules', {'game': 'whoami'})
        assert rules.structured_content == {'game': 'whoami', 'rules': '# whoami\nrules text'}
        left = await client.call_tool('leave_lobby', {'player_session': HANDLE})
        assert left.structured_content['ok']
    assert fake.actions == [('codenames_join_team', {'team': 'red'})]


@pytest.mark.asyncio
async def test_gateway_bearer_is_deployment_token_not_player_handle():
    called = False

    async def inner(scope, receive, send):
        nonlocal called
        called = True

    middleware = BearerMiddleware(inner, 'deployment-token')

    async def receive(): return {'type': 'http.disconnect'}
    sent = []
    async def send(message): sent.append(message)
    await middleware({'type': 'http', 'headers': [(b'authorization', b'Bearer mgps_player_one')]},
                     receive, send)
    assert sent[0]['status'] == 401 and not called
    await middleware({'type': 'http', 'headers': [(b'authorization', b'Bearer deployment-token')]},
                     receive, send)
    assert called

import asyncio

from starlette.testclient import TestClient

from meme_games.apps.codenames.actions import ActionRejected, codenames_actions
from meme_games.apps.codenames.domain import CODENAMES, CardColor, GamePhase, TeamColor, WordCard
from meme_games.core import DI
from meme_games.domain import AgentAccessService, LobbyService, UserManager, lobby_events
from meme_games.main import app


lobbies = DI.get(LobbyService)
users = DI.get(UserManager)
agents = DI.get(AgentAccessService)


def create_agent_lobby(lobby_id):
    host = users.create(name=f'host-{lobby_id}', named=True)
    lobby = lobbies.create_lobby(host, lobby_id, CODENAMES)
    access, token = agents.create(lobby.id, 'Robot Alice')
    return lobby, access, token


def internal_headers(token=None):
    headers = {'X-Meme-Games-Gateway': 'test-gateway'}
    if token: headers['Authorization'] = f'Bearer {token}'
    return headers


def test_agent_tokens_are_hashed_scoped_and_revocable():
    lobby, access, token = create_agent_lobby('agent-token')
    assert token not in access.token_hash
    assert agents.verify(token, touch=False).lobby_id == lobby.id
    agents.revoke(access.id, lobby.id)
    assert agents.verify(token, touch=False) is None


def test_private_api_adds_agent_and_never_leaks_hidden_colors(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby, access, token = create_agent_lobby('agent-state')
    with TestClient(app, raise_server_exceptions=False) as client:
        identity = client.get('/internal/agents/identity', headers=internal_headers(token))
        assert identity.status_code == 200
        member = lobby.get_member(access.user_uid)
        assert member and member.user.kind == 'agent' and not member.is_player

        joined = client.post('/internal/agents/action', headers=internal_headers(token),
                             json={'action': 'join_team', 'arguments': {'team': 'red'}})
        assert joined.json()['ok']
        lobby.state.phase = GamePhase.GUESSING
        lobby.state.turn = TeamColor.RED
        lobby.state.board = [WordCard('secret', CardColor.BLUE)]
        state = client.get('/internal/agents/state', headers=internal_headers(token)).json()
        assert state['board'][0] == {'id': lobby.state.board[0].id, 'word': 'secret', 'revealed': False}

        lobby.state.phase = GamePhase.WAITING
        lobby.state.spymasters.add(member.uid)
        state = client.get('/internal/agents/state', headers=internal_headers(token)).json()
        assert state['board'][0]['color'] == 'blue'


def test_private_api_rejects_wrong_gateway_and_revoked_agent(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby, access, token = create_agent_lobby('agent-auth')
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get('/internal/agents/state', headers={'Authorization': f'Bearer {token}'}).status_code == 401
        agents.revoke(access.id, lobby.id)
        assert client.get('/internal/agents/state', headers=internal_headers(token)).status_code == 401


def test_codenames_action_publishes_one_revisioned_event():
    lobby, access, _ = create_agent_lobby('agent-events')
    member = lobby.create_member(users.get(access.user_uid))
    seen = []
    unsubscribe = lobby_events.subscribe(lambda event, _: seen.append(event) if event.lobby_id == lobby.id else None)
    try: asyncio.run(codenames_actions.join_team(lobby, member, 'red'))
    finally: unsubscribe()
    assert lobby.revision == 1
    assert len(seen) == 1
    assert seen[0].topics == frozenset({'roster'})


def test_conflicting_reveals_are_serialized():
    lobby, access, _ = create_agent_lobby('agent-race')
    member = lobby.create_member(users.get(access.user_uid))
    member.play()
    lobby.state.players[member.uid] = TeamColor.RED
    lobby.state.phase = GamePhase.GUESSING
    lobby.state.turn = TeamColor.RED
    card = WordCard('race', CardColor.RED)
    lobby.state.board = [card]

    async def race():
        return await asyncio.gather(
            codenames_actions.reveal_card(lobby, member, card.id),
            codenames_actions.reveal_card(lobby, member, card.id), return_exceptions=True)

    results = asyncio.run(race())
    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, ActionRejected) for result in results) == 1

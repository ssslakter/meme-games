import asyncio

from starlette.testclient import TestClient

from meme_games.apps.codenames.actions import ActionRejected, codenames_actions
from meme_games.apps.codenames.domain import CODENAMES, CardColor, GamePhase, TeamColor, WordCard
from meme_games.apps.whoami.actions import whoami_actions
from meme_games.apps.whoami.domain import WHOAMI
from meme_games.core import DI
from meme_games.domain import AgentPlayerSessionService, LobbyService, UserManager, lobby_events
from meme_games.main import app


lobbies = DI.get(LobbyService)
users = DI.get(UserManager)
sessions = DI.get(AgentPlayerSessionService)


def create_lobby(lobby_id, allow_agents=True):
    host = users.create(name=f'host-{lobby_id}', named=True)
    return lobbies.create_lobby(host, lobby_id, CODENAMES, allow_agents=allow_agents)


def create_whoami_lobby(lobby_id):
    host = users.create(name=f'host-{lobby_id}', named=True)
    lobby = lobbies.create_lobby(host, lobby_id, WHOAMI, allow_agents=True)
    lobby.get_member(host.uid).play()
    return lobby


def headers(secret='test-gateway'): return {'X-Meme-Games-Gateway': secret}


def join(client, lobby, name):
    return client.post('/internal/agents/join', headers=headers(),
                       json={'lobby_code': lobby.id, 'name': name})


def post(client, endpoint, handle, **data):
    return client.post(f'/internal/agents/{endpoint}', headers=headers(),
                       json={'player_session': handle, **data})


def error(response): return response.text.strip('"')


def test_two_shared_gateway_clients_get_independent_players(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby = create_lobby('agent-pairs')
    with TestClient(app, raise_server_exceptions=False) as client:
        alice = join(client, lobby, 'Robot Alice').json()
        bob = join(client, lobby, 'Robot Bob').json()
        assert alice['player_session'] != bob['player_session']
        assert sessions.get(alice['player_session']).handle_hash != alice['player_session']
        assert post(client, 'action', alice['player_session'], action='codenames_join_team',
                    arguments={'team': 'red'}).json()['ok']
        assert post(client, 'action', bob['player_session'], action='codenames_join_team',
                    arguments={'team': 'blue'}).json()['ok']
        assert post(client, 'action', alice['player_session'], action='codenames_set_role',
                    arguments={'role': 'spymaster'}).json()['ok']
        a_state = post(client, 'state', alice['player_session']).json()
        b_state = post(client, 'state', bob['player_session']).json()
    assert a_state['you']['team'] == 'red' and a_state['you']['role'] == 'spymaster'
    assert b_state['you']['team'] == 'blue' and b_state['you']['role'] == 'operative'


def test_join_rejections_and_name_normalization(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    disabled = create_lobby('agents-off', allow_agents=False)
    enabled = create_lobby('agents-on')
    with TestClient(app, raise_server_exceptions=False) as client:
        assert error(join(client, disabled, 'Alice')) == 'agents_disabled'
        missing = client.post('/internal/agents/join', headers=headers(),
                              json={'lobby_code': 'missing', 'name': 'Alice'})
        assert missing.status_code == 404 and missing.json()['detail'] == 'lobby_not_found'
        first = join(client, enabled, '  Robot   Alice  ')
        assert first.json()['name'] == 'Robot Alice'
        duplicate = join(client, enabled, 'robot alice')
        assert duplicate.status_code == 409 and error(duplicate) == 'name_taken'
        assert error(join(client, enabled, 'x' * 41)) == 'invalid_name'
        enabled.lock()
        assert error(join(client, enabled, 'Bob')) == 'lobby_locked'
        assert join(client, enabled, 'Eve',).status_code == 409
        assert client.post('/internal/agents/join', headers=headers('wrong'),
                           json={'lobby_code': enabled.id, 'name': 'Eve'}).status_code == 401


def test_disabling_blocks_new_joins_but_existing_session_continues(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby = create_lobby('disable-later')
    with TestClient(app, raise_server_exceptions=False) as client:
        handle = join(client, lobby, 'Alice').json()['player_session']
        lobby.allow_agents = False
        assert error(join(client, lobby, 'Bob')) == 'agents_disabled'
        assert post(client, 'state', handle).status_code == 200


def test_hidden_state_is_receiver_specific(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby = create_lobby('agent-state')
    with TestClient(app, raise_server_exceptions=False) as client:
        operative = join(client, lobby, 'Operative').json()['player_session']
        spymaster = join(client, lobby, 'Spymaster').json()['player_session']
        post(client, 'action', operative, action='codenames_join_team', arguments={'team': 'red'})
        post(client, 'action', spymaster, action='codenames_join_team', arguments={'team': 'red'})
        post(client, 'action', spymaster, action='codenames_set_role', arguments={'role': 'spymaster'})
        lobby.state.board = [WordCard('secret', CardColor.BLUE)]
        op_card = post(client, 'state', operative).json()['board'][0]
        spy_card = post(client, 'state', spymaster).json()['board'][0]
    assert 'color' not in op_card
    assert spy_card['color'] == 'blue'


def test_leave_closes_handle_and_removes_only_its_member(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby = create_lobby('agent-leave')
    with TestClient(app, raise_server_exceptions=False) as client:
        alice = join(client, lobby, 'Alice').json()['player_session']
        bob = join(client, lobby, 'Bob').json()['player_session']
        alice_uid = sessions.get(alice).user_uid
        bob_uid = sessions.get(bob).user_uid
        lobby.lock()
        blocked = post(client, 'leave', alice)
        assert blocked.status_code == 409 and error(blocked) == 'lobby_locked'
        assert alice_uid in lobby.members and sessions.get(alice)
        lobby.unlock()
        assert post(client, 'leave', alice).json()['ok']
        assert alice_uid not in lobby.members and bob_uid in lobby.members
        assert post(client, 'state', alice).status_code == 401
        assert post(client, 'state', bob).status_code == 200


def test_events_are_durable_ordered_generic_and_reconnectable(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby = create_lobby('agent-events-api')
    with TestClient(app, raise_server_exceptions=False) as client:
        joined = join(client, lobby, 'Alice').json()
        cursor = joined['cursor']
        asyncio.run(lobby_events.publish(lobby, 'roster'))
        asyncio.run(lobby_events.publish(lobby, 'game'))
        payload = post(client, 'events', joined['player_session'], cursor=cursor,
                       timeout_seconds=1).json()
        assert post(client, 'state', joined['player_session']).json()['you']['name'] == 'Alice'
    assert [event['sequence'] for event in payload['events']] == [cursor + 1, cursor + 2]
    assert payload['next_cursor'] == cursor + 2
    assert all(set(event) == {'sequence', 'type', 'revision'} for event in payload['events'])


def test_whoami_agent_boundary_flow_is_personalized(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby = create_whoami_lobby('whoami-agent')
    host = lobby.host
    with TestClient(app, raise_server_exceptions=False) as client:
        joined = join(client, lobby, 'Robot').json()
        handle = joined['player_session']
        agent_uid = sessions.get(handle).user_uid
        assert lobby.members[agent_uid].is_player
        state = post(client, 'state', handle).json()
        assert state['you']['card_to_write']['id'] == host.uid
        assert post(client, 'action', handle, action='whoami_write_card',
                    arguments={'text': 'Sherlock Holmes'}).json()['ok']
        asyncio.run(whoami_actions.write_card(lobby, host, 'A friendly robot'))
        asyncio.run(whoami_actions.start(lobby, host))

        asyncio.run(whoami_actions.ask_question(lobby, host, 'Am I fictional?'))
        state = post(client, 'state', handle).json()
        assert state['question']['text'] == 'Am I fictional?'
        assert 'whoami_answer_question' in state['available_actions']
        assert post(client, 'action', handle, action='whoami_answer_question',
                    arguments={'answer': 'yes'}).json()['ok']
        asyncio.run(whoami_actions.end_turn(lobby, host))

        state = post(client, 'state', handle).json()
        own = next(player for player in state['players'] if player['id'] == agent_uid)
        assert 'card' not in own
        assert state['you']['is_current_turn']
        assert {'whoami_ask_question', 'whoami_end_turn'} <= set(state['available_actions'])
        assert post(client, 'action', handle, action='whoami_ask_question',
                    arguments={'question': 'Am I electronic?'}).json()['ok']
        assert post(client, 'action', handle, action='whoami_write_note',
                    arguments={'text': 'Possibly a machine'}).json()['ok']
        asyncio.run(whoami_actions.write_note(lobby, host, 'Shared human deduction'))
        shared = post(client, 'state', handle).json()
        assert next(player for player in shared['players'] if player['id'] == host.uid)['notes'] == 'Shared human deduction'
        lobby.state.config.private_notes = True
        private = post(client, 'state', handle).json()
        assert 'notes' not in next(player for player in private['players'] if player['id'] == host.uid)
        assert post(client, 'action', handle, action='whoami_end_turn', arguments={}).json()['ok']
    assert lobby.state.player(agent_uid).notes == 'Possibly a machine'
    assert lobby.state.current_turn_uid == host.uid


def test_codenames_action_publishes_one_revisioned_event():
    lobby = create_lobby('agent-action-event')
    user = users.create(name='Agent', named=True, kind='agent')
    member = lobby.create_member(user)
    seen = []
    unsubscribe = lobby_events.subscribe(lambda event, _: seen.append(event) if event.lobby_id == lobby.id else None)
    try: asyncio.run(codenames_actions.join_team(lobby, member, 'red'))
    finally: unsubscribe()
    assert lobby.revision == 1 and len(seen) == 1


def test_conflicting_reveals_are_serialized():
    lobby = create_lobby('agent-race')
    member = lobby.create_member(users.create(name='Agent', named=True, kind='agent'))
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

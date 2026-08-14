import asyncio

from starlette.testclient import TestClient

from meme_games.apps.codenames.actions import ActionRejected, codenames_actions
from meme_games.apps.codenames.domain import CODENAMES, CardColor, GamePhase, TeamColor, WordCard
from meme_games.apps.shared.chat import say_as
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


def read_state(client, handle):
    '''A full read. Ordinary reads answer with only what changed since the last one.'''
    return post(client, 'state', handle, full=True).json()['state']


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
        a_state = read_state(client, alice['player_session'])
        b_state = read_state(client, bob['player_session'])
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


def test_state_reads_return_only_what_changed(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby = create_whoami_lobby('agent-delta')
    with TestClient(app, raise_server_exceptions=False) as client:
        handle = join(client, lobby, 'Robot').json()['player_session']
        first = post(client, 'state', handle).json()
        assert first['full'] and 'players' in first['state']

        unchanged = post(client, 'state', handle).json()
        assert not unchanged['full'] and unchanged['changes'] == {}
        # what you may do is never withheld as "unchanged"
        assert 'whoami_write_card' in unchanged['available_actions']
        assert unchanged['you']['card_to_write']['id'] == lobby.host.uid
        assert unchanged['phase'] == 'waiting'

        asyncio.run(whoami_actions.set_topic(lobby, lobby.host, 'Cartoons'))
        moved = post(client, 'state', handle).json()
        assert not moved['full']
        assert moved['changes']['topic'] == 'Cartoons'
        assert 'players' not in moved['changes']
        assert 'whoami_write_card' in moved['available_actions']

        assert post(client, 'state', handle, full=True).json()['full']


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
        op_card = read_state(client, operative)['board'][0]
        spy_card = read_state(client, spymaster)['board'][0]
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
        assert post(client, 'leave', alice).json()['ok']
        assert not lobby.locked  # a round cannot continue a player short
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
        assert read_state(client, joined['player_session'])['you']['name'] == 'Alice'
    assert [event['sequence'] for event in payload['events']] == [cursor + 1, cursor + 2]
    assert payload['next_cursor'] == cursor + 2
    assert all(set(event) == {'sequence', 'revision', 'topics', 'happened'}
               for event in payload['events'])
    assert [event['topics'] for event in payload['events']] == [['roster'], ['game']]


def test_whoami_agent_boundary_flow_is_personalized(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby = create_whoami_lobby('whoami-agent')
    host = lobby.host
    with TestClient(app, raise_server_exceptions=False) as client:
        joined = join(client, lobby, 'Robot').json()
        handle = joined['player_session']
        agent_uid = sessions.get(handle).user_uid
        assert lobby.members[agent_uid].is_player
        state = read_state(client, handle)
        assert state['you']['card_to_write']['id'] == host.uid
        assert post(client, 'action', handle, action='whoami_write_card',
                    arguments={'text': 'Sherlock Holmes'}).json()['ok']
        asyncio.run(whoami_actions.write_card(lobby, host, 'A friendly robot'))
        asyncio.run(whoami_actions.start(lobby, host))

        asyncio.run(whoami_actions.ask_question(lobby, host, 'Am I fictional?'))
        state = read_state(client, handle)
        assert state['question']['text'] == 'Am I fictional?'
        assert 'whoami_answer_question' in state['available_actions']
        assert post(client, 'action', handle, action='whoami_answer_question',
                    arguments={'answer': 'yes'}).json()['ok']
        asyncio.run(whoami_actions.end_turn(lobby, host))

        state = read_state(client, handle)
        own = next(player for player in state['players'] if player['id'] == agent_uid)
        assert 'card' not in own
        assert state['you']['is_current_turn']
        assert {'whoami_ask_question', 'whoami_end_turn'} <= set(state['available_actions'])
        assert post(client, 'action', handle, action='whoami_ask_question',
                    arguments={'question': 'Am I electronic?'}).json()['ok']
        asyncio.run(whoami_actions.answer_question(lobby, host, 'no'))
        blocked = post(client, 'action', handle, action='whoami_ask_question',
                       arguments={'question': 'Am I alive?'})
        assert blocked.status_code == 409
        assert blocked.json()['message'] == 'Your turn must end after a no answer'
        assert 'whoami_ask_question' not in read_state(client, handle)['available_actions']
        assert post(client, 'action', handle, action='whoami_write_note',
                    arguments={'text': 'Possibly a machine'}).status_code == 409
        asyncio.run(whoami_actions.write_note(lobby, host, 'Shared human deduction'))
        shared = read_state(client, handle)
        assert next(player for player in shared['players'] if player['id'] == host.uid)['notes'] == 'Shared human deduction'
        lobby.state.config.private_notes = True
        private = read_state(client, handle)
        assert 'notes' not in next(player for player in private['players'] if player['id'] == host.uid)
        assert post(client, 'action', handle, action='whoami_end_turn', arguments={}).json()['ok']
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


def test_events_report_what_moved_even_when_the_content_is_hidden(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby = create_whoami_lobby('agent-event-detail')
    host = lobby.host
    with TestClient(app, raise_server_exceptions=False) as client:
        joined = join(client, lobby, 'Robot').json()
        handle, cursor = joined['player_session'], joined['cursor']
        agent = lobby.members[sessions.get(handle).user_uid]

        # the agent writes the host's card, and the host writes the agent's
        assert post(client, 'action', handle, action='whoami_write_card',
                    arguments={'text': 'Sherlock Holmes'}).json()['ok']
        asyncio.run(whoami_actions.write_card(lobby, host, 'A friendly robot'))
        asyncio.run(whoami_actions.write_note(lobby, host, 'thinking...'))
        asyncio.run(whoami_actions.set_topic(lobby, host, 'Detectives'))

        payload = post(client, 'events', handle, cursor=cursor, timeout_seconds=1).json()

    happened = [line for event in payload['events'] for line in event['happened']]
    # an event carries what happened, not a nudge to go and read it
    assert f'{agent.name} wrote "Sherlock Holmes" on {host.name}\'s card' in happened
    assert f'{host.name} now has these notes: "thinking..."' in happened
    assert any('the topic is now "Detectives"' in line for line in happened)
    # the one thing this player may not hear is the text of their own card
    assert any(f'{host.name} wrote your card' in line for line in happened)
    assert all('A friendly robot' not in line for line in happened)


def test_the_card_can_be_rewritten_outside_your_turn(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby = create_whoami_lobby('agent-write-anytime')
    host = lobby.host
    with TestClient(app, raise_server_exceptions=False) as client:
        handle = join(client, lobby, 'Robot').json()['player_session']
        agent_uid = sessions.get(handle).user_uid
        post(client, 'action', handle, action='whoami_write_card', arguments={'text': 'first'})
        asyncio.run(whoami_actions.write_card(lobby, host, 'A friendly robot'))
        asyncio.run(whoami_actions.start(lobby, host))
        assert lobby.state.current_turn_uid == host.uid  # not the agent's turn

        assert post(client, 'action', handle, action='whoami_write_card',
                    arguments={'text': 'second'}).json()['ok']
        assert 'whoami_write_card' in read_state(client, handle)['available_actions']
    assert lobby.state.player(host.uid).label_text == 'second'


def test_a_topic_change_marks_the_card_you_wrote_as_out_of_date(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby = create_whoami_lobby('agent-stale-card')
    host = lobby.host
    with TestClient(app, raise_server_exceptions=False) as client:
        handle = join(client, lobby, 'Robot').json()['player_session']
        asyncio.run(whoami_actions.set_topic(lobby, host, 'Scientists'))
        post(client, 'action', handle, action='whoami_write_card',
             arguments={'text': 'Albert Einstein'})

        fresh = read_state(client, handle)['you']['card_to_write']
        assert fresh['text'] == 'Albert Einstein'
        assert not fresh['written_under_an_older_topic']

        asyncio.run(whoami_actions.set_topic(lobby, host, 'Famous politicians'))
        stale = read_state(client, handle)['you']['card_to_write']
        assert stale['written_under_an_older_topic']
        assert 'whoami_write_card' in read_state(client, handle)['available_actions']

        # rewriting under the new topic clears it again
        post(client, 'action', handle, action='whoami_write_card',
             arguments={'text': 'Winston Churchill'})
        assert not read_state(client, handle)['you']['card_to_write']['written_under_an_older_topic']


def test_the_topic_event_says_cards_need_rewriting(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby = create_whoami_lobby('agent-topic-event')
    with TestClient(app, raise_server_exceptions=False) as client:
        joined = join(client, lobby, 'Robot').json()
        asyncio.run(whoami_actions.set_topic(lobby, lobby.host, 'Famous politicians'))
        payload = post(client, 'events', joined['player_session'],
                       cursor=joined['cursor'], timeout_seconds=1).json()

    happened = [line for event in payload['events'] for line in event['happened']]
    assert any('Famous politicians' in line and 'rewritten' in line for line in happened)
    assert 'hint' not in payload


def test_the_event_stream_alone_is_enough_to_follow_the_game(monkeypatch):
    '''Reading an event must never require a follow-up state call to learn what it was.'''
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby = create_whoami_lobby('agent-event-content')
    host = lobby.host
    with TestClient(app, raise_server_exceptions=False) as client:
        joined = join(client, lobby, 'Robot').json()
        handle, cursor = joined['player_session'], joined['cursor']
        post(client, 'action', handle, action='whoami_write_card', arguments={'text': 'Ada Lovelace'})
        asyncio.run(whoami_actions.write_card(lobby, host, 'A friendly robot'))
        asyncio.run(whoami_actions.start(lobby, host))
        asyncio.run(whoami_actions.ask_question(lobby, host, 'Am I fictional?'))
        payload = post(client, 'events', handle, cursor=cursor, timeout_seconds=1).json()
        asked = [line for event in payload['events'] for line in event['happened']]

        cursor = payload['next_cursor']
        post(client, 'action', handle, action='whoami_answer_question', arguments={'answer': 'no'})
        asyncio.run(whoami_actions.end_turn(lobby, host))
        answered = [line for event in post(client, 'events', handle, cursor=cursor,
                                           timeout_seconds=1).json()['events']
                    for line in event['happened']]

    assert any(f'{host.name} asked "Am I fictional?"' in line and 'Robot' in line for line in asked)
    assert any('the game is playing' in line for line in asked)
    assert any('answered "Am I fictional?" with no' in line for line in answered)
    assert any('turn now' in line for line in answered)


def test_an_event_keeps_the_facts_it_was_born_with(monkeypatch):
    '''Facts are captured when the event happens, so later moves cannot rewrite history.'''
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby = create_whoami_lobby('agent-event-history')
    host = lobby.host
    with TestClient(app, raise_server_exceptions=False) as client:
        joined = join(client, lobby, 'Robot').json()
        handle, cursor = joined['player_session'], joined['cursor']
        post(client, 'action', handle, action='whoami_write_card', arguments={'text': 'first guess'})
        post(client, 'action', handle, action='whoami_write_card', arguments={'text': 'second guess'})
        happened = [line for event in post(client, 'events', handle, cursor=cursor,
                                           timeout_seconds=1).json()['events']
                    for line in event['happened']]

    assert any('"first guess"' in line for line in happened)
    assert any('"second guess"' in line for line in happened)


def _ready_codenames(lobby_id):
    '''A codenames lobby with both teams filled and a spymaster each.'''
    lobby = create_lobby(lobby_id)
    host = lobby.get_member(lobby.host.uid)
    mates = [lobby.create_member(users.create(name=f'{name}-{lobby_id}', named=True))
             for name in ('bob', 'zoe')]
    for member, team in ((host, 'red'), (mates[0], 'blue'), (mates[1], 'blue')):
        asyncio.run(codenames_actions.join_team(lobby, member, team))
    asyncio.run(codenames_actions.set_role(lobby, host, 'spymaster'))
    asyncio.run(codenames_actions.set_role(lobby, mates[0], 'spymaster'))
    return lobby, host


def test_codenames_events_carry_the_clue_the_card_and_the_turn(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby, host = _ready_codenames('cn-events')
    with TestClient(app, raise_server_exceptions=False) as client:
        joined = join(client, lobby, 'Robot').json()
        handle = joined['player_session']
        agent = lobby.members[sessions.get(handle).user_uid]
        asyncio.run(codenames_actions.join_team(lobby, agent, 'red'))
        asyncio.run(codenames_actions.start(lobby, host))

        state = lobby.state
        state.turn, state.phase = state.team_of(host), GamePhase.CLUE
        cursor = lobby.revision
        asyncio.run(codenames_actions.give_clue(lobby, host, 'animal', 2))
        neutral = next(card for card in state.board if card.color == CardColor.NEUTRAL)
        assert post(client, 'action', handle, action='codenames_reveal_card',
                    arguments={'card_id': neutral.id}).json()['ok']

        payload = post(client, 'events', handle, cursor=cursor, timeout_seconds=1).json()
        hidden = {card.word for card in state.board if not card.revealed}

    happened = [line for event in payload['events'] for line in event['happened']]
    assert f'{host.name} gave the red team the clue "animal" for 2' in happened
    assert f'the red team turned over "{neutral.word}" - it was neutral' in happened
    assert any('passes to the blue team' in line for line in happened)
    assert any('cards still hidden' in line for line in happened)
    # the key is never in the stream: an unrevealed word must not appear at all
    assert not [word for word in hidden if any(word in line for line in happened)]


def test_a_yes_answer_says_how_many_questions_are_left(monkeypatch):
    '''A "yes" leaves the turn open; the event has to say so rather than leave the
    reader to work it out from a question count and a rule in a tool description.'''
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby = create_whoami_lobby('agent-questions-left')
    host = lobby.host
    with TestClient(app, raise_server_exceptions=False) as client:
        handle = join(client, lobby, 'Robot').json()['player_session']
        post(client, 'action', handle, action='whoami_write_card', arguments={'text': 'Ada'})
        asyncio.run(whoami_actions.write_card(lobby, host, 'A friendly robot'))
        asyncio.run(whoami_actions.start(lobby, host))
        state = lobby.state
        state.current_turn_uid = next(uid for uid in state.turn_order if uid != host.uid)

        cursor = lobby.revision
        post(client, 'action', handle, action='whoami_ask_question', arguments={'question': 'Am I alive?'})
        asyncio.run(whoami_actions.answer_question(lobby, host, 'yes'))
        after_yes = post(client, 'state', handle).json()
        yes_lines = [line for event in post(client, 'events', handle, cursor=cursor,
                                            timeout_seconds=1).json()['events']
                     for line in event['happened']]

        cursor = lobby.revision
        post(client, 'action', handle, action='whoami_ask_question', arguments={'question': 'Am I real?'})
        asyncio.run(whoami_actions.answer_question(lobby, host, 'no'))
        after_no = post(client, 'state', handle).json()
        no_lines = [line for event in post(client, 'events', handle, cursor=cursor,
                                           timeout_seconds=1).json()['events']
                    for line in event['happened']]

    assert after_yes['you']['is_current_turn'] and after_yes['you']['questions_left'] == 2
    assert 'whoami_ask_question' in after_yes['available_actions']
    assert any('with yes - Robot may ask 2 more questions this turn' in line for line in yes_lines)

    assert after_no['you']['questions_left'] == 0
    assert 'whoami_ask_question' not in after_no['available_actions']
    assert any('with no - Robot must end their turn now' in line for line in no_lines)


def test_chat_reaches_everyone_and_is_available_in_every_game(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby = create_whoami_lobby('agent-chat')
    host = lobby.host
    with TestClient(app, raise_server_exceptions=False) as client:
        joined = join(client, lobby, 'Robot').json()
        handle, cursor = joined['player_session'], joined['cursor']
        assert 'lobby_say' in read_state(client, handle)['available_actions']

        assert post(client, 'action', handle, action='lobby_say',
                    arguments={'text': 'your card is Dragon, you got it!'}).json()['ok']
        asyncio.run(say_as(lobby, host, 'nice one'))

        happened = [line for event in post(client, 'events', handle, cursor=cursor,
                                           timeout_seconds=1).json()['events']
                    for line in event['happened']]
        chat = read_state(client, handle)['chat']

        # chat is lobby-level, so it survives a switch to another game
        lobby.play_game(CODENAMES)
        assert 'lobby_say' in read_state(client, handle)['available_actions']

    assert 'Robot said in chat: "your card is Dragon, you got it!"' in happened
    assert f'{host.name} said in chat: "nice one"' in happened
    assert [message['text'] for message in chat] == ['your card is Dragon, you got it!', 'nice one']


def test_an_empty_chat_message_is_refused(monkeypatch):
    monkeypatch.setenv('MCP_GATEWAY_SECRET', 'test-gateway')
    lobby = create_whoami_lobby('agent-chat-empty')
    with TestClient(app, raise_server_exceptions=False) as client:
        handle = join(client, lobby, 'Robot').json()['player_session']
        blocked = post(client, 'action', handle, action='lobby_say', arguments={'text': '   '})
        assert blocked.status_code == 409
    assert not lobby.chat

"""The Who Am I board: what each player is allowed to see, and what survives a restart."""
from fasthtml.common import to_xml

import asyncio

from meme_games.apps.whoami.actions import whoami_actions
from meme_games.apps.whoami.components.cards import PlayerCard, PlayerLabelText
from meme_games.apps.whoami.components.game import Game, TopicBanner
from meme_games.apps.whoami.components.notes import NotesCard, QuestionPanel
from meme_games.apps.whoami.domain import WHOAMI, WhoAmIPhase, WhoAmIState
from meme_games.core import DI
from meme_games.domain import GAME_REGISTRY, LobbyService, User
from meme_games.domain.user import UserManager

service = DI.get(LobbyService)
um = DI.get(UserManager)


def _lobby(id):
    host = um.create(name=f'host-{id}')
    lobby = service.create_lobby(host, id, WHOAMI)
    host_member = lobby.get_member(host.uid)
    other = lobby.create_member(um.create(name=f'other-{id}'))
    host_member.play(), other.play()
    return lobby, host_member, other


def test_card_and_label_positions_survive_a_restart():
    lobby, host, _ = _lobby('wai1')
    lobby.state.player(host.uid).set_card_pos(410, 120)
    lobby.state.player(host.uid).set_label_transform(dict(x=-30, y=-90, width=200, height=90))

    spec = GAME_REGISTRY[WHOAMI]
    restored: WhoAmIState = spec.from_dict(spec.to_dict(lobby.state))

    assert restored.player(host.uid).card_pos.x == 410
    assert restored.player(host.uid).label_tfm.y == -90
    assert restored.player(host.uid).label_tfm.width == 200


def test_config_survives_a_restart():
    lobby, _, _ = _lobby('wai2')
    lobby.state.config.private_notes = True

    spec = GAME_REGISTRY[WHOAMI]
    assert spec.from_dict(spec.to_dict(lobby.state)).config.private_notes


def test_turn_and_question_survive_persistence():
    lobby, first, second = _lobby('wai-persist-turn')
    lobby.state.player(first.uid).set_label('First')
    lobby.state.player(second.uid).set_label('Second')
    lobby.state.start([first.uid, second.uid])
    lobby.state.ask(first, 'Am I fictional?')

    spec = GAME_REGISTRY[WHOAMI]
    restored = spec.from_dict(spec.to_dict(lobby.state))

    assert restored.phase == WhoAmIPhase.PLAYING
    assert restored.current_turn_uid == first.uid
    assert restored.question.text == 'Am I fictional?'


def test_state_written_before_positions_existed_still_loads():
    spec = GAME_REGISTRY[WHOAMI]
    old = {'players': {'u1': {'label_text': 'Shrek', 'label_tfm': None, 'notes': 'green'}}}

    restored: WhoAmIState = spec.from_dict(old)

    assert restored.player('u1').label_text == 'Shrek'
    assert restored.player('u1').card_pos is None
    assert not restored.config.private_notes


def test_a_player_never_receives_their_own_label():
    lobby, host, other = _lobby('wai3')
    lobby.state.player(host.uid).set_label('Shrek')

    own = to_xml(PlayerCard(host, host, lobby))
    theirs = to_xml(PlayerCard(other, host, lobby))

    assert 'Shrek' not in own
    assert 'Shrek' in theirs


def test_private_notes_hide_other_players_pads_only():
    lobby, host, other = _lobby('wai4')
    data = lobby.state.player(host.uid)
    data.set_notes('my deductions')

    assert NotesCard(other, host, data, lobby.state) is not None

    lobby.state.config.private_notes = True
    assert NotesCard(other, host, data, lobby.state) is None
    assert NotesCard(host, host, data, lobby.state) is not None


def test_the_label_owner_gets_a_marker_instead_of_the_text():
    lobby, host, _ = _lobby('wai5')
    data = lobby.state.player(host.uid)
    data.set_label('Shrek')

    marker = to_xml(PlayerLabelText(host, host, data)[1])

    assert '>?<' in marker


def test_only_users_without_a_name_of_their_own_are_asked_for_one():
    assert User('u', 'Guest').needs_name
    assert not User('u', 'Kate').needs_name
    assert not User('u', 'Guest', named=True).needs_name


def test_card_author_is_previous_player_and_others_are_read_only():
    lobby, host, other = _lobby('wai-author')
    third = lobby.create_member(um.create(name='third-author'))
    third.play()

    authored = to_xml(PlayerLabelText(host, other, lobby.state.player(other.uid), lobby))
    observed = to_xml(PlayerLabelText(third, other, lobby.state.player(other.uid), lobby))

    assert 'ws-send' in authored and 'readonly' not in authored
    assert 'readonly' in observed and 'ws-send' not in observed


def test_start_uses_player_entry_order_and_requires_every_card():
    lobby, first, second = _lobby('wai-start')
    assert not lobby.state.start([first.uid, second.uid])
    lobby.state.player(first.uid).set_label('First identity')
    lobby.state.player(second.uid).set_label('Second identity')

    asyncio.run(whoami_actions.start(lobby, first))
    assert lobby.state.phase == WhoAmIPhase.PLAYING
    assert lobby.locked
    assert lobby.state.current_turn_uid == first.uid
    assert lobby.state.previous_player(first.uid) == second.uid


def test_host_joining_last_asks_last_and_locked_board_has_no_join_card():
    host = um.create(name='late-host')
    lobby = service.create_lobby(host, 'wai-late-host', WHOAMI)
    guest = lobby.create_member(um.create(name='early-guest'))
    guest.play()
    lobby.host.play()
    lobby.state.player(guest.uid).set_label('Guest')
    lobby.state.player(host.uid).set_label('Host')

    asyncio.run(whoami_actions.start(lobby, lobby.host))

    assert lobby.state.turn_order == [guest.uid, host.uid]
    assert lobby.state.current_turn_uid == guest.uid
    assert 'Join the game' not in to_xml(Game(User('spectator', 'Spectator'), lobby))


def test_question_permissions_latest_only_and_manual_turn_end():
    lobby, first, second = _lobby('wai-questions')
    lobby.state.player(first.uid).set_label('First')
    lobby.state.player(second.uid).set_label('Second')
    lobby.state.start([first.uid, second.uid])

    assert lobby.state.ask(first, 'Am I alive?')
    assert not lobby.state.ask(first, 'Another?')
    assert not lobby.state.answer(first, 'yes')
    assert lobby.state.answer(second, 'no')
    assert lobby.state.ask(first, 'Am I fictional?')
    assert lobby.state.question.text == 'Am I fictional?'
    assert lobby.state.end_turn(first)
    assert lobby.state.current_turn_uid == second.uid and lobby.state.question is None


def test_agent_boundaries_render_controls_but_human_pair_does_not():
    lobby, human, agent = _lobby('wai-boundary')
    agent.user.kind = 'agent'
    lobby.state.player(human.uid).set_label('Human')
    lobby.state.player(agent.uid).set_label('Agent')
    lobby.state.start([human.uid, agent.uid])

    human_turn = to_xml(QuestionPanel(human, human, lobby))
    assert 'Ask a yes/no question' in human_turn
    lobby.state.current_turn_uid = agent.uid
    lobby.state.ask(agent, 'Am I a person?')
    agent_turn_for_answerer = to_xml(QuestionPanel(human, agent, lobby))
    assert '>Yes<' in agent_turn_for_answerer and '>Not sure<' in agent_turn_for_answerer

    agent.user.kind = 'human'
    assert 'Ask a yes/no question' not in to_xml(QuestionPanel(human, agent, lobby))


def test_agent_to_agent_question_is_fully_domain_driven():
    lobby, first, second = _lobby('wai-agent-pair')
    first.user.kind = second.user.kind = 'agent'
    lobby.state.player(first.uid).set_label('First')
    lobby.state.player(second.uid).set_label('Second')
    lobby.state.start([first.uid, second.uid])

    asyncio.run(whoami_actions.ask_question(lobby, first, 'Am I human?'))
    asyncio.run(whoami_actions.answer_question(lobby, second, 'not_sure'))

    assert lobby.state.question.answer == 'not_sure'
    assert 'Ask a yes/no question' not in to_xml(QuestionPanel(first, first, lobby))


def test_topic_banner_uses_everything_fallback():
    lobby, _, _ = _lobby('wai-topic')
    assert '>Everything<' in to_xml(TopicBanner(lobby))
    lobby.state.config.topic = 'Movie characters'
    assert '>Movie characters<' in to_xml(TopicBanner(lobby))


def test_restart_preserves_topic_positions_and_settings_only():
    lobby, host, other = _lobby('wai-restart')
    state = lobby.state
    state.config.topic = 'Cartoon characters'
    state.config.private_notes = True
    state.player(host.uid).set_card_pos(20, 30)
    state.player(host.uid).set_label('Shrek')
    state.player(host.uid).set_notes('green')
    state.player(other.uid).set_label('Donkey')
    state.start([host.uid, other.uid])

    asyncio.run(whoami_actions.restart(lobby, host))

    assert state.phase == WhoAmIPhase.WAITING and not lobby.locked
    assert state.config.topic == 'Cartoon characters' and state.config.private_notes
    assert state.player(host.uid).card_pos.x == 20
    assert state.player(host.uid).label_text == state.player(host.uid).notes == ''

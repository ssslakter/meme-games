"""Hive Mind: secret answers, what agrees with what, and who gets to see it."""
import asyncio

from fasthtml.common import to_xml
from starlette.testclient import TestClient

from meme_games.apps.hivemind.actions import ActionRejected, hivemind_actions
from meme_games.apps.hivemind.components import AnswerArea, Game, HiveMindSettings, RevealBoard
from meme_games.apps.hivemind.domain import (ANSWER_MAX, DEFAULT_ROUNDS, HIVEMIND, HiveMindState,
                                            HivePhase, normalize_answer)
from meme_games.apps.word_packs.domain import WordPack, WordPackRepo
from meme_games.core import DI
from meme_games.domain import LobbyService
from meme_games.domain.user import UserManager
from meme_games.main import app

service = DI.get(LobbyService)
um = DI.get(UserManager)
BROWSER = {'user-agent': 'Mozilla/5.0 Firefox'}


def _game(id, players=3, rounds=DEFAULT_ROUNDS):
    host = um.create(name=f'host-{id}')
    lobby = service.create_lobby(host, id, HIVEMIND)
    members = [lobby.get_member(host.uid)]
    for index in range(players - 1):
        members.append(lobby.create_member(um.create(name=f'p{index}-{id}')))
    for member in members: member.play()
    lobby.state.total_rounds = rounds
    return lobby, members


def _playing(id, answers, players=3, rounds=DEFAULT_ROUNDS):
    """A lobby with one round open and `answers` written, keyed by player position."""
    lobby, members = _game(id, players, rounds)
    state: HiveMindState = lobby.state
    assert state.start([member.uid for member in members])
    for index, text in answers.items(): assert state.submit(members[index].uid, text)
    return lobby, members, state


#---------------------------------#
#------------- Scoring -----------#
#---------------------------------#

def test_a_shared_answer_scores_and_a_unique_one_does_not():
    lobby, members, state = _playing('hive-score', {0: 'Pizza!', 1: '  pizza ', 2: 'pineapple'})
    assert state.all_answered([member.uid for member in members])
    assert state.reveal()

    assert state.score(members[0].uid) == 1, 'the same answer in another letter case agrees'
    assert state.score(members[1].uid) == 1
    assert state.score(members[2].uid) == 0, 'nobody else wrote it'
    played = state.last()
    assert played.groups() == {'pizza': [members[0].uid, members[1].uid]}
    assert played.uniques() == {members[2].uid: 'pineapple'}


def test_a_big_group_and_a_pair_pay_the_same_point():
    _, members, state = _playing('hive-groups', {0: 'a', 1: 'a', 2: 'a'})
    state.reveal()
    assert [state.score(member.uid) for member in members] == [1, 1, 1]


def test_normalize_answer_ignores_case_spacing_and_trailing_punctuation():
    assert normalize_answer('  New   YORK! ') == 'new york'
    assert normalize_answer('Так') == normalize_answer('так')
    assert normalize_answer('  ') == ''


def test_the_open_round_is_emptied_when_it_is_revealed():
    _, _, state = _playing('hive-leak', {0: 'pizza', 1: 'pizza', 2: 'sushi'})
    assert state.reveal()
    assert state.answers == {}, 'the reveal is the only record from now on'
    assert state.last().answers


def test_a_player_who_leaves_is_dropped_from_the_rounds_they_played():
    _, members, state = _playing('hive-leave', {0: 'pizza', 1: 'pizza', 2: 'sushi'})
    state.reveal()
    state.remove_player(members[2].uid)
    assert members[2].uid not in state.last().answers
    assert state.totals().get(members[2].uid) is None


#-------------------------------#
#------------- Rounds ----------#
#-------------------------------#

def test_rounds_run_out_and_a_short_deck_starts_over():
    state = HiveMindState(wordpack=WordPack(name='Two', words_='one\ntwo'))
    assert state.set_total_rounds(3)
    assert state.start(['a', 'b'])
    questions = []
    for _ in range(3):
        questions.append(state.question)
        state.submit('a', 'shared'), state.submit('b', 'shared')
        assert state.reveal()
        state.next_round()
    assert questions == ['one', 'two', 'one'], 'the deck cycles'
    assert state.finished
    assert not state.next_round(), 'a finished game does not deal again'
    assert state.score('a') == 3


def test_a_game_needs_two_players_and_a_deck():
    state = HiveMindState()
    assert not state.can_start(['a']), 'one player has nobody to agree with'
    assert state.can_start(['a', 'b'])
    assert not state.reveal(), 'nothing to reveal before the game starts'
    assert not HiveMindState(wordpack=None).can_start(['a', 'b'])
    assert not HiveMindState(wordpack=WordPack(name='Empty')).can_start(['a', 'b'])
    assert state.start(['a', 'b'])
    assert not state.all_answered(['a', 'b'])
    assert state.submit('a', 'pizza')
    assert not state.all_answered(['a', 'b'])
    assert state.submit('b', 'pizza')
    assert state.all_answered(['a', 'b'])


def test_answers_are_capped_replaced_and_only_taken_while_the_round_is_open():
    state = HiveMindState()
    state.start(['a', 'b'])
    assert not state.submit('a', '')
    assert not state.submit('a', 'x' * (ANSWER_MAX + 1))
    assert state.submit('a', 'pizza')
    assert state.submit('a', 'calzone'), 'submitting again replaces the answer'
    assert state.answers == {'a': 'calzone'}
    state.reveal()
    assert not state.submit('a', 'too late')


def test_a_spectator_cannot_leave_an_answer():
    lobby, _, state = _playing('hive-spectator-answer', {0: 'pizza'})
    watcher = lobby.create_member(um.create(name='watcher-hive-spectator-answer'))
    try:
        asyncio.run(hivemind_actions.submit(lobby, watcher, 'sneaky'))
        raise AssertionError('a spectator must not answer')
    except ActionRejected: pass
    assert watcher.uid not in state.answers


#-------------------------------#
#----------- The board ---------#
#-------------------------------#

def test_the_open_round_never_shows_another_players_answer():
    lobby, members, state = _playing('hive-secret', {1: 'truffle oil'})

    markup = to_xml(Game(members[0], lobby))
    assert 'truffle oil' not in markup, 'a secret answer must not reach the board, not even hidden'
    assert '1 of 3 answered' in markup
    assert 'data-ui="hivemind-answer"' in markup and 'name="answer"' in markup

    assert 'Your answer is in' in to_xml(AnswerArea(members[1], lobby))
    assert 'Your answer is in' not in to_xml(AnswerArea(members[0], lobby))


def test_a_spectator_gets_the_join_card_instead_of_an_input():
    lobby, _, state = _playing('hive-spectator', {0: 'pizza'})
    watcher = um.create(name='watcher-hive-spectator')
    markup = to_xml(Game(watcher, lobby))
    assert 'data-ui="hivemind-join"' in markup and 'Join the game' in markup
    assert 'name="answer"' not in markup


def test_the_reveal_lists_matches_first_and_then_the_ones_on_their_own():
    lobby, members, state = _playing('hive-reveal', {0: 'pizza', 1: 'pizza', 2: 'sushi'})
    state.reveal()

    markup = to_xml(RevealBoard(members[0], lobby))
    assert 'data-ui="hivemind-match"' in markup and 'data-ui="hivemind-unique"' in markup
    assert markup.index('pizza') < markup.index('sushi'), 'agreements lead, loners follow'


def test_the_winner_is_named_only_once_the_last_round_is_revealed():
    lobby, members, state = _playing('hive-winner', {0: 'pizza', 1: 'pizza', 2: 'sushi'}, rounds=2)
    state.reveal()
    assert not state.finished
    assert 'Winner' not in to_xml(Game(members[0], lobby)), 'a match in play has no winner'

    assert state.next_round()
    for member in members: state.submit(member.uid, 'x')
    state.reveal()
    assert state.finished and not state.next_round()

    markup = to_xml(Game(members[0], lobby))
    assert 'Winner: host-hive-winner, p0-hive-winner with 2 points' in markup
    assert 'data-winner="true"' in markup


def test_only_the_host_gets_settings_and_they_name_the_deck():
    lobby, members = _game('hive-settings', players=2)
    assert HiveMindSettings(members[0], lobby) is not None
    assert HiveMindSettings(members[1], lobby) is None
    markup = to_xml(HiveMindSettings(members[0], lobby))
    assert 'Prompts' in markup and '24 questions' in markup
    assert 'data-ui="hivemind-deck"' in markup


#------------------------------#
#------------ Routes ----------#
#------------------------------#

def _client(ip): return TestClient(app, client=(ip, 1), raise_server_exceptions=False)


def test_a_full_game_over_http():
    with _client('172.20.0.1') as host, _client('172.20.0.2') as guest:
        host.get('/hivemind/hive-http', headers=BROWSER)
        guest.get('/hivemind/hive-http', headers=BROWSER)
        lobby = service.lobbies['hive-http']
        host.post('/hivemind/play', headers=BROWSER)
        guest.post('/hivemind/play', headers=BROWSER)
        assert all(member.is_player for member in lobby.members.values())

        host.post('/hivemind/start_game', headers=BROWSER)
        assert lobby.state.phase == HivePhase.WRITING and lobby.locked

        host.post('/hivemind/submit_answer?answer=Pizza', headers=BROWSER)
        guest.post('/hivemind/submit_answer?answer=pizza', headers=BROWSER)
        host.post('/hivemind/advance', headers=BROWSER)
        assert lobby.state.phase == HivePhase.REVEAL
        assert all(lobby.state.score(member.uid) == 1 for member in lobby.members.values())

        host.post('/hivemind/advance', headers=BROWSER)
        assert lobby.state.round_number == 2 and lobby.state.phase == HivePhase.WRITING

        host.post('/hivemind/restart_game', headers=BROWSER)
        assert lobby.state.phase == HivePhase.WAITING and not lobby.locked


def test_the_answer_a_player_typed_never_reaches_another_players_page():
    with _client('172.20.0.3') as host, _client('172.20.0.4') as guest:
        host.get('/hivemind/hive-http2', headers=BROWSER)
        guest.get('/hivemind/hive-http2', headers=BROWSER)
        host.post('/hivemind/play', headers=BROWSER)
        guest.post('/hivemind/play', headers=BROWSER)
        host.post('/hivemind/start_game', headers=BROWSER)
        guest.post('/hivemind/submit_answer?answer=secret-word', headers=BROWSER)

        page = host.get('/hivemind/hive-http2', headers=BROWSER).text
        assert 'secret-word' not in page
        assert '1 of 2 answered' in page


def test_a_guest_cannot_drive_the_host_controls():
    with _client('172.20.0.5') as host, _client('172.20.0.6') as guest:
        host.get('/hivemind/hive-guest', headers=BROWSER)
        guest.get('/hivemind/hive-guest', headers=BROWSER)
        lobby = service.lobbies['hive-guest']
        host.post('/hivemind/play', headers=BROWSER)
        guest.post('/hivemind/play', headers=BROWSER)

        guest.post('/hivemind/start_game', headers=BROWSER)
        assert lobby.state.phase == HivePhase.WAITING
        guest.post('/hivemind/advance', headers=BROWSER)
        guest.post('/hivemind/update_settings?total_rounds=19', headers=BROWSER)
        guest.post('/hivemind/select_pack?id=whatever', headers=BROWSER)
        assert lobby.state.total_rounds == DEFAULT_ROUNDS
        assert lobby.state.wordpack.name == 'Prompts'


def test_the_host_can_pick_another_deck_between_games():
    with _client('172.20.0.7') as host:
        host.get('/hivemind/hive-deck', headers=BROWSER)
        lobby = service.lobbies['hive-deck']
        pack = DI.get(WordPackRepo).find('Default')

        host.post(f'/hivemind/select_pack?id={pack.id}', headers=BROWSER)
        assert lobby.state.wordpack.id == pack.id

        host.post('/hivemind/play', headers=BROWSER)
        host.post('/hivemind/update_settings?total_rounds=3', headers=BROWSER)
        assert lobby.state.total_rounds == 3
        host.post('/hivemind/start_game', headers=BROWSER)  # one player: refused
        assert lobby.state.phase == HivePhase.WAITING

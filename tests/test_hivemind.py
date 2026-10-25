"""Hive Mind: word lists, what agrees with what, the clock, and who gets to see it."""
import asyncio

from fasthtml.common import to_xml
from starlette.testclient import TestClient

from meme_games.apps.hivemind.actions import ActionRejected, hivemind_actions
from meme_games.apps.hivemind.components import AnswerArea, Game, HiveMindSettings, RevealBoard
from meme_games.apps.hivemind.domain import (ANSWERS_PER_ROUND, ANSWER_MAX, DEFAULT_ROUNDS,
                                            DEFAULT_SECONDS, HIVEMIND, HiveMindState, HivePhase,
                                            normalize_answer)
from meme_games.apps.word_packs.domain import WordPack, WordPackRepo
from meme_games.core import DI
from meme_games.domain import LobbyService
from meme_games.domain.user import UserManager
from meme_games.main import app

service = DI.get(LobbyService)
um = DI.get(UserManager)
BROWSER = {'user-agent': 'Mozilla/5.0 Firefox'}


def _game(id, players=3, rounds=DEFAULT_ROUNDS, seconds=None):
    """`seconds=None` keeps the domain default clock; pass 0 for no clock at all."""
    host = um.create(name=f'host-{id}')
    lobby = service.create_lobby(host, id, HIVEMIND)
    members = [lobby.get_member(host.uid)]
    for index in range(players - 1):
        members.append(lobby.create_member(um.create(name=f'p{index}-{id}')))
    for member in members: member.play()
    lobby.state.total_rounds = rounds
    if seconds is not None: lobby.state.seconds = seconds
    return lobby, members


def _write(state: HiveMindState, member, words):
    for index, word in enumerate(words): assert state.set_word(member.uid, index, word)


def _playing(id, lists, players=3, rounds=DEFAULT_ROUNDS, seconds=None):
    """A lobby with one round open and the players' lists written, by position."""
    lobby, members = _game(id, players, rounds, seconds)
    state: HiveMindState = lobby.state
    assert state.start([member.uid for member in members])
    for index, words in lists.items(): _write(state, members[index], words)
    return lobby, members, state


#---------------------------------#
#------------- Scoring -----------#
#---------------------------------#

def test_every_word_somebody_else_wrote_scores_a_point():
    lobby, members, state = _playing('hive-score', {0: ['Pizza!', 'cheese', 'basil'],
                                                    1: ['  pizza ', 'cheese', 'oregano'],
                                                    2: ['pineapple', 'cheese']})
    assert state.reveal()

    assert state.score(members[0].uid) == 2, 'pizza and cheese'
    assert state.score(members[1].uid) == 2
    assert state.score(members[2].uid) == 1, 'cheese only - pineapple and the rest are loners'
    played = state.last()
    assert played.matches()['cheese'] == sorted(member.uid for member in members)
    assert played.points() == {members[0].uid: 2, members[1].uid: 2, members[2].uid: 1}


def test_a_word_one_player_repeats_neither_scores_nor_matches():
    _, members, state = _playing('hive-dup', {0: ['pizza', 'pizza'], 1: ['sushi']})
    state.reveal()
    assert state.score(members[0].uid) == 0, 'nobody else wrote it, however many cells it fills'
    assert state.last().matches() == {}


def test_normalize_answer_ignores_case_spacing_and_trailing_punctuation():
    assert normalize_answer('  New   YORK! ') == 'new york'
    assert normalize_answer('Так') == normalize_answer('так')
    assert normalize_answer('  ') == ''


def test_revealing_empties_the_open_round():
    _, _, state = _playing('hive-leak', {0: ['pizza'], 1: ['pizza']})
    assert state.reveal()
    assert state.answers == {} and state.ready == set(), 'the reveal is the only record now'
    assert state.last().words(list(state.last().answers)[0]) == ['pizza']


def test_a_player_who_leaves_is_dropped_from_the_rounds_they_played():
    _, members, state = _playing('hive-leave', {0: ['pizza'], 1: ['pizza']})
    state.reveal()
    state.remove_player(members[1].uid)
    assert members[1].uid not in state.last().answers
    assert state.totals().get(members[1].uid) is None


#-------------------------------#
#------------- Rounds ----------#
#-------------------------------#

def test_rounds_run_out_and_a_short_deck_starts_over():
    state = HiveMindState(wordpack=WordPack(name='Two', words_='one\ntwo'), seconds=0)
    assert state.set_total_rounds(3)
    assert state.start(['a', 'b'])
    questions = []
    for _ in range(3):
        questions.append(state.question)
        state.set_word('a', 0, 'shared'), state.set_word('b', 0, 'shared')
        assert state.reveal()
        state.next_round()
    assert questions == ['one', 'two', 'one'], 'the deck cycles'
    assert state.finished and not state.next_round()
    assert state.score('a') == 3


def test_a_game_needs_two_players_and_a_deck_and_cells_are_bounded():
    state = HiveMindState(seconds=0)
    assert not state.can_start(['a']), 'one player has nobody to agree with'
    assert state.can_start(['a', 'b'])
    assert not HiveMindState(wordpack=None).can_start(['a', 'b'])
    assert not HiveMindState(wordpack=WordPack(name='Empty')).can_start(['a', 'b'])
    assert not state.reveal(), 'nothing to reveal before the game starts'

    assert state.start(['a', 'b'])
    assert not state.set_word('a', ANSWERS_PER_ROUND, 'one cell too far')
    assert not state.set_word('a', -1, 'no such cell')
    assert not state.set_word('a', 0, 'x' * (ANSWER_MAX + 1))
    assert state.set_word('a', 3, 'pizza'), 'any cell can be used'
    assert state.words('a') == ['pizza']
    assert state.set_word('a', 3, ''), 'a cell can be emptied again'
    assert state.words('a') == []


def test_being_done_is_what_closes_a_round():
    state = HiveMindState(seconds=0)
    state.start(['a', 'b'])
    assert state.set_ready('a') and not state.all_ready(['a', 'b'])
    assert not state.set_word('a', 0, 'late'), 'a player who is done cannot keep writing'
    assert state.set_ready('a', False), 'but can take it back to keep writing'
    assert state.set_word('a', 0, 'pizza')
    assert state.set_ready('a') and state.set_ready('b') and state.all_ready(['a', 'b'])
    assert state.reveal() and not state.all_ready(['a', 'b'])


def test_the_clock_is_armed_by_the_hosts_seconds_and_stopped_when_the_round_closes():
    state = HiveMindState(seconds=45)
    state.start(['a', 'b'])
    assert state.timer.total == 45 and not state.timer.stop_.is_set(), 'the clock is running'

    assert state.timeout() and state.phase == HivePhase.REVEAL
    assert state.timer.stop_.is_set(), 'a closed round leaves no clock running'


def test_no_seconds_means_no_clock_at_all():
    state = HiveMindState(seconds=0)
    state.start(['a', 'b'])
    assert state.timer.stop_.is_set()
    state.reveal()
    assert state.next_round() and state.timer.stop_.is_set()


def test_editing_a_word_after_the_reveal_re_decides_the_score():
    _, members, state = _playing('hive-edit', {0: ['pepperoni pizza'], 1: ['pizza']})
    state.reveal()
    assert state.score(members[0].uid) == 0

    assert state.edit_word(members[0].uid, 0, 'Pizza!'), 'its author can reword it'
    assert state.score(members[0].uid) == 1 and state.score(members[1].uid) == 1
    assert not state.edit_word(members[0].uid, 7, 'no such cell')
    assert not state.edit_word(members[0].uid, 0, 'x' * (ANSWER_MAX + 1))


#-------------------------------#
#----------- The board ---------#
#-------------------------------#

def test_the_open_round_never_shows_another_players_words():
    lobby, members, state = _playing('hive-secret', {1: ['truffle oil', 'basil']})

    markup = to_xml(Game(members[0], lobby))
    assert 'truffle oil' not in markup and 'basil' not in markup
    assert markup.count('data-ui="hivemind-cell"') == ANSWERS_PER_ROUND
    assert 'data-ui="hivemind-word"' not in markup, 'words only go on the board after a reveal'

    assert AnswerArea(members[0], lobby) is not None
    assert AnswerArea(um.create(name='watcher-hive-secret'), lobby) is None


def test_a_spectator_gets_the_join_card_instead_of_cells():
    lobby, _, state = _playing('hive-spectator', {0: ['pizza']})
    markup = to_xml(Game(um.create(name='watcher-hive-spectator'), lobby))
    assert 'data-ui="hivemind-cell"' not in markup
    assert 'data-ui="hivemind-join"' in markup


def test_the_reveal_marks_agreed_words_and_only_their_author_may_edit_them():
    lobby, members, state = _playing('hive-reveal', {0: ['pizza', 'basil'], 1: ['pizza'],
                                                     2: ['sushi']})
    state.reveal()

    host_view = to_xml(RevealBoard(members[0], lobby)), 'the host may rewrite every word'
    markup = host_view[0]
    assert markup.count('data-matched="true"') == 2 and markup.count('data-matched="false"') == 2
    assert 'readonly' not in markup
    assert 'Words that agreed' in markup and 'pizza' in markup

    other_player = to_xml(RevealBoard(members[1], lobby))
    assert other_player.count('readonly') == 3, 'a player may only rewrite their own word'


def test_the_winner_is_named_only_once_the_last_round_is_revealed():
    lobby, members, state = _playing('hive-winner', {0: ['pizza'], 1: ['pizza'], 2: ['sushi']},
                                     rounds=2)
    state.reveal()
    assert not state.finished
    assert 'Winner' not in to_xml(Game(members[0], lobby)), 'a match in play has no winner'

    assert state.next_round()
    for member in members: _write(state, member, ['x'])
    state.reveal()
    assert state.finished and not state.next_round()

    markup = to_xml(Game(members[0], lobby))
    assert 'Winner: host-hive-winner, p0-hive-winner with 2 points' in markup
    assert 'data-winner="true"' in markup


def test_the_scoreboard_rides_on_the_left_of_the_board():
    lobby, members, state = _playing('hive-layout', {0: ['pizza']})
    markup = to_xml(Game(members[0], lobby))
    assert 'lg:grid-cols-[18rem_minmax(0,1fr)]' in markup
    assert markup.index('hivemind-scoreboard') < markup.index('hivemind-question'), \
        'the scoreboard column comes first, the board is centred next to it'


def test_only_the_host_gets_settings_and_they_name_the_deck():
    lobby, members = _game('hive-settings', players=2)
    assert HiveMindSettings(members[0], lobby) is not None
    assert HiveMindSettings(members[1], lobby) is None
    markup = to_xml(HiveMindSettings(members[0], lobby))
    assert 'Prompts' in markup and 'data-ui="hivemind-deck"' in markup
    assert f'value="{DEFAULT_SECONDS}"' in markup, 'the clock is a host setting'


#------------------------------#
#------------ Routes ----------#
#------------------------------#

def _client(ip): return TestClient(app, client=(ip, 1), raise_server_exceptions=False)


def _join(client, lobby_id, uid=None):
    client.get(f'/hivemind/{lobby_id}', headers=BROWSER)
    client.post('/hivemind/play', headers=BROWSER)


def test_a_full_game_over_http():
    with _client('172.20.0.1') as host, _client('172.20.0.2') as guest:
        _join(host, 'hive-http'), _join(guest, 'hive-http')
        lobby = service.lobbies['hive-http']
        assert all(member.is_player for member in lobby.members.values())

        host.post('/hivemind/start_game', headers=BROWSER)
        assert lobby.state.phase == HivePhase.WRITING and lobby.locked

        host.post('/hivemind/set_word?index=0', data={'text': 'Pizza'}, headers=BROWSER)
        guest.post('/hivemind/set_word?index=0', data={'text': 'pizza'}, headers=BROWSER)
        assert lobby.state.words(lobby.host.uid) == ['Pizza']

        host.post('/hivemind/set_ready', headers=BROWSER)
        assert lobby.state.phase == HivePhase.WRITING, 'one player still writing'
        guest.post('/hivemind/set_ready', headers=BROWSER)
        assert lobby.state.phase == HivePhase.REVEAL, 'everyone ready closes the round'
        assert all(lobby.state.score(member.uid) == 1 for member in lobby.members.values())

        # the host can decide that a near miss counts, and the scores follow
        host_uid = lobby.host.uid
        host.post(f'/hivemind/edit_word?uid={host_uid}&index=0', data={'text': 'sushi'},
                  headers=BROWSER)
        assert lobby.state.score(host_uid) == 0

        host.post('/hivemind/advance', headers=BROWSER)
        assert lobby.state.round_number == 2 and lobby.state.phase == HivePhase.WRITING

        host.post('/hivemind/restart_game', headers=BROWSER)
        assert lobby.state.phase == HivePhase.WAITING and not lobby.locked


def test_words_never_reach_another_players_page_before_the_reveal():
    with _client('172.20.0.3') as host, _client('172.20.0.4') as guest:
        _join(host, 'hive-http2'), _join(guest, 'hive-http2')
        host.post('/hivemind/start_game', headers=BROWSER)
        guest.post('/hivemind/set_word?index=0', data={'text': 'secret-word'}, headers=BROWSER)
        guest.post('/hivemind/set_ready', headers=BROWSER)

        page = host.get('/hivemind/hive-http2', headers=BROWSER).text
        assert 'secret-word' not in page
        assert '1 of 2 done' in page, 'the others only get the count'


def test_a_guest_cannot_drive_the_controls_or_rewrite_someone_elses_word():
    with _client('172.20.0.5') as host, _client('172.20.0.6') as guest:
        _join(host, 'hive-guest'), _join(guest, 'hive-guest')
        lobby = service.lobbies['hive-guest']
        host_uid = lobby.host.uid

        guest.post('/hivemind/start_game', headers=BROWSER)
        assert lobby.state.phase == HivePhase.WAITING
        guest.post('/hivemind/update_settings?total_rounds=19&seconds=5', headers=BROWSER)
        assert lobby.state.total_rounds == DEFAULT_ROUNDS
        assert lobby.state.seconds == DEFAULT_SECONDS
        guest.post('/hivemind/select_pack?id=whatever', headers=BROWSER)
        assert lobby.state.wordpack.name == 'Prompts'

        host.post('/hivemind/start_game', headers=BROWSER)
        host.post('/hivemind/set_word?index=0', data={'text': 'pizza'}, headers=BROWSER)
        host.post('/hivemind/set_ready', headers=BROWSER)
        guest.post('/hivemind/set_ready', headers=BROWSER)
        guest.post(f'/hivemind/edit_word?uid={host_uid}&index=0', data={'text': 'hijacked'},
                   headers=BROWSER)
        assert lobby.state.last().words(host_uid) == ['pizza']


def test_a_spectator_cannot_write_at_all():
    lobby, _, state = _playing('hive-spectator-write', {0: ['pizza']})
    watcher = lobby.create_member(um.create(name='watcher-hive-spectator-write'))
    for call in (hivemind_actions.set_word(lobby, watcher, 0, 'sneaky'),
                 hivemind_actions.set_ready(lobby, watcher)):
        try:
            asyncio.run(call)
            raise AssertionError('a spectator must not write')
        except ActionRejected: pass
    assert watcher.uid not in state.answers and watcher.uid not in state.ready


def test_the_host_can_set_the_clock_and_it_closes_the_round_by_itself():
    with _client('172.20.0.7') as host:
        _join(host, 'hive-clock')
        lobby = service.lobbies['hive-clock']
        host.post('/hivemind/play', headers=BROWSER)
        host.post('/hivemind/update_settings?total_rounds=2&seconds=1', headers=BROWSER)
        assert lobby.state.seconds == 1

    lobby, members = _game('hive-clock-run', players=2, seconds=1)

    async def play_out():
        await hivemind_actions.start(lobby, lobby.host)
        await asyncio.sleep(1.4)

    asyncio.run(play_out())
    assert lobby.state.phase == HivePhase.REVEAL, 'the clock closes the round on its own'

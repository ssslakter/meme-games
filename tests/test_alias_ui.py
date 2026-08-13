import asyncio

from fasthtml.common import to_xml

from meme_games.apps.alias.components.game import Game
from meme_games.apps.alias.components.settings import HostGameActions
from meme_games.apps.alias.components.word_panel import GuessCount, GuessPanel, WordEntry, WordPanel
from meme_games.apps.alias.domain import ALIAS, GameState, GuessEntry
from meme_games.apps.alias.domain.game import StateMachine
from meme_games.apps.alias.domain.team import Team
from meme_games.apps.alias.routes import set_end_round_timer
from meme_games.domain import Lobby, LobbyMember, User


def test_round_entries_show_result_but_hide_points():
    game = GameState(state=StateMachine.ROUND_PLAYING)

    guessed = to_xml(WordEntry(GuessEntry('apple', 1), game))
    skipped = to_xml(WordEntry(GuessEntry('pear', 0), game))

    assert 'data-result="guessed"' in guessed
    assert 'data-result="skipped"' in skipped
    assert 'Score:' not in guessed + skipped
    assert 'px-3 py-2' in guessed + skipped


def test_review_entries_expose_score_controls():
    game = GameState(state=StateMachine.REVIEWING)
    entry = to_xml(WordEntry(GuessEntry('apple', 1), game))

    assert 'Score:' in entry
    assert '>+</button>' in entry
    assert '>-</button>' in entry


def test_review_moves_history_back_to_the_center():
    member = LobbyMember(user=User('player', 'Player'))
    game = GameState(
        state=StateMachine.REVIEWING,
        active_team=Team(members=[member]),
        active_player=member,
        guess_log=[GuessEntry('apple', 1)],
    )

    panel = to_xml(WordPanel(member, game))

    assert 'data-stage="review"' in panel
    assert 'data-ui="round-history"' in panel
    assert 'data-ui="round-center"' not in panel


def test_empty_round_keeps_oob_history_target():
    panel = to_xml(GuessPanel(GameState(state=StateMachine.ROUND_PLAYING)))

    assert 'id="guess_log"' in panel
    assert 'Words will appear here' in panel
    assert '>Guessed<' not in panel
    assert '>Skipped<' not in panel


def test_guess_count_is_an_oob_update():
    game = GameState(state=StateMachine.ROUND_PLAYING, guess_log=[GuessEntry('apple', 1)])
    count = to_xml(GuessCount(game))

    assert 'id="guess_count"' in count
    assert 'hx-swap-oob="true"' in count
    assert '>1</span>' in count


def test_round_stacks_history_under_teams_beside_center():
    member = LobbyMember(user=User('player-layout', 'Player'))
    team = Team(members=[member])
    game = GameState(
        state=StateMachine.ROUND_PLAYING,
        teams={team.id: team}, active_team=team, active_player=member,
        active_word='banana',
    )
    game.timer.set(game.config.time_limit)
    lobby = Lobby(current_game=ALIAS, states={ALIAS: game}, members={member.uid: member})

    board = to_xml(Game(member, lobby))

    assert 'data-ui="alias-teams"' in board
    assert 'data-ui="alias-stage"' in board
    assert 'data-ui="round-history"' in board
    assert 'lg:max-h-[calc(100vh-7rem)]' in board
    assert 'lg:overflow-hidden' in board
    assert 'data-ui="alias-history"' not in board
    assert board.index('data-ui="alias-teams"') < board.index('data-ui="round-history"') < board.index('data-ui="alias-stage"')


def test_timer_expiry_marks_the_last_word_without_ending_round():
    member = LobbyMember(user=User('last-word-player', 'Player'))
    team = Team(members=[member])
    game = GameState(state=StateMachine.ROUND_PLAYING, active_team=team,
                     active_player=member, active_word='banana')
    game.timer.set(game.config.time_limit)
    lobby = Lobby(current_game=ALIAS, states={ALIAS: game}, members={member.uid: member})

    async def finish_timer():
        game.timer.finished = True

    game.timer.sleep = finish_timer
    asyncio.run(set_end_round_timer(lobby))

    panel = to_xml(WordPanel(member, game))
    assert game.state == StateMachine.ROUND_PLAYING
    assert 'data-phase="last-word"' in panel
    assert 'Time is up — last word' in panel


def test_restart_preserves_teams_and_resets_match_state():
    member = LobbyMember(user=User('restart-player', 'Player'))
    team = Team(members=[member], points=12, times_played=2)
    game = GameState(state=StateMachine.REVIEWING, teams={team.id: team}, active_team=team,
                     active_player=member, guess_log=[GuessEntry('apple', 1)], votes={member.uid})

    game.restart()

    assert game.state == StateMachine.WAITING_FOR_PLAYERS
    assert game.teams[team.id].members == [member]
    assert team.points == team.times_played == 0
    assert not game.guess_log and not game.votes


def test_shuffle_preserves_team_sizes_and_each_member_once():
    members = [LobbyMember(user=User(f'shuffle-{i}', f'Player {i}')) for i in range(4)]
    first, second = Team(members=members[:1]), Team(members=members[1:])
    game = GameState(teams={first.id: first, second.id: second})

    game.shuffle_teams()

    assert [len(first), len(second)] == [1, 3]
    assert {m.uid for team in game.teams.values() for m in team.members} == {m.uid for m in members}


def test_alias_host_gets_game_management_controls():
    host = LobbyMember(user=User('controls-host', 'Host'), is_host_=True)
    guest = LobbyMember(user=User('controls-guest', 'Guest'))
    html = to_xml(HostGameActions(host, GameState()))

    assert 'Pause' in html and 'Restart' in html
    assert 'Shuffle teams' in html and 'Random wordpack' in html
    assert HostGameActions(guest, GameState()) is None

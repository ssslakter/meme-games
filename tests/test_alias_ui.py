import asyncio

from fasthtml.common import to_xml

from meme_games.apps.alias.components.game import Game
from meme_games.apps.alias.components.settings import HostGameActions, VoteButton
from meme_games.apps.alias.components.word_panel import GuessCount, GuessPanel, WordEntry, WordPanel
from meme_games.apps.alias.domain import ALIAS, GameState, GuessEntry
from meme_games.apps.alias.domain.config import GameConfig
from meme_games.apps.alias.domain.game import StateMachine
from meme_games.apps.alias.domain.team import Team
from meme_games.apps.alias.routes import set_end_round_timer
from meme_games.apps.user.components.general import Avatar
from meme_games.apps.word_packs.domain import WordPack
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


def test_one_team_scores_the_explaining_pair_without_repeating_pairs():
    players = [LobbyMember(user=User(f'pair-{i}', f'Player {i}')) for i in range(4)]
    team = Team(members=players)
    game = GameState(config=GameConfig(wordpack=WordPack(words_='apple'), max_score=2),
                     teams={team.id: team})

    game.start_game()
    pairs = set()

    for _ in range(6):
        pairs.add(frozenset((game.active_player.uid, game.active_guesser.uid)))
        game.next_state()  # start round
        game.guess_log = [GuessEntry('apple', 1)]
        game.next_state()  # review
        game.next_state()  # confirm review and advance

    assert len(pairs) == 6
    assert max(game.explanation_counts.values()) - min(game.explanation_counts.values()) <= 1
    assert game.check_win_condition()


def test_wordpack_ignores_blank_lines():
    assert WordPack(words_='apple\n\n pear \n \r\n').words == ['apple', 'pear']


def test_lobby_avatar_is_clipped_to_a_circle():
    html = to_xml(Avatar(User('avatar-player', 'Player')))

    assert 'rounded-full' in html and 'object-cover' in html


def test_first_round_still_waits_for_the_explainer_to_start():
    players = [LobbyMember(user=User(f'ready-{i}', f'Player {i}')) for i in range(2)]
    team = Team(members=players)
    game = GameState(state=StateMachine.VOTING_TO_START, teams={team.id: team},
                     active_team=team, active_player=players[0], votes={p.uid for p in players})

    assert 'Start round' in to_xml(VoteButton(players[0], game))


def test_review_confirmation_is_the_next_team_ready_check():
    scorer = LobbyMember(user=User('scorer', 'Scorer'))
    next_player = LobbyMember(user=User('next-player', 'Next player'))
    first, second = Team(members=[scorer]), Team(members=[next_player])
    game = GameState(state=StateMachine.REVIEWING, teams={first.id: first, second.id: second},
                     active_team=second, active_player=next_player, review_team=first,
                     review_player=scorer, guess_log=[GuessEntry('apple', 1)], votes={next_player.uid})

    game.next_state(reset_votes=False)

    assert first.points == 1
    assert game.state == StateMachine.VOTING_TO_START
    assert game.votes == {next_player.uid}
    assert 'Start round' in to_xml(VoteButton(next_player, game))


def test_player_words_are_reused_for_the_one_word_second_round():
    player = LobbyMember(user=User('word-writer', 'Writer'))
    team = Team(members=[player])
    game = GameState(config=GameConfig(player_words=True, word_collection_time=30),
                     teams={team.id: team})

    game.start_game()
    game.submit_words(player, 'apple\n\npear')
    assert game.finish_word_collection()
    assert game.state == StateMachine.VOTING_TO_START

    game.next_state()
    assert game.word_round == 1 and game.active_word in {'apple', 'pear'}
    assert not game.guess_word(player, True)
    assert not game.guess_word(player, True)
    assert game.word_round == 2 and game.active_word in {'apple', 'pear'}
    assert not game.guess_word(player, True)
    assert game.guess_word(player, True)
    game.next_state()
    game.next_state()
    assert game.state == StateMachine.FINISHED

import asyncio

from fasthtml.common import to_xml

from meme_games.apps.alias.components.game import Game, Page
from meme_games.apps.alias.components.settings import ConfigLobby, GameControls, HostGameActions, PackSelect, PackSelectButton, PackSelectContents, RestartConfirmation, VoteButton
from meme_games.apps.alias.components.word_panel import CurrentWord, ExplainerPanel, GuessCount, GuessPanel, RoundLog, WordCollectionPanel, WordEntry, WordPanel
from meme_games.apps.alias.domain import ALIAS, GameState, GuessEntry
from meme_games.apps.alias.domain.config import GameConfig
from meme_games.apps.alias.domain.game import StateMachine
from meme_games.apps.alias.domain.team import Team
from meme_games.apps.alias.routes import set_end_round_timer, set_end_word_collection_timer
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


def test_review_keeps_the_round_layout():
    member = LobbyMember(user=User('player', 'Player'))
    game = GameState(
        state=StateMachine.REVIEWING,
        active_team=Team(members=[member]),
        active_player=member,
        guess_log=[GuessEntry('apple', 1)],
    )

    panel = to_xml(WordPanel(member, game))

    assert 'data-stage="review"' in panel
    assert panel.index('data-ui="round-center"') < panel.index('data-ui="round-history"')
    assert "I'm ready" in panel


def test_empty_round_keeps_oob_history_target():
    panel = to_xml(GuessPanel(None, GameState(state=StateMachine.ROUND_PLAYING)))

    assert 'id="guess_log"' in panel
    assert 'Words will appear here' in panel
    assert '>Guessed<' not in panel
    assert '>Skipped<' not in panel


def test_guess_count_is_an_oob_update():
    game = GameState(state=StateMachine.ROUND_PLAYING, guess_log=[GuessEntry('apple', 1)])
    count = to_xml(GuessCount(None, game))

    assert 'id="guess_count"' in count
    assert 'hx-swap-oob="true"' in count
    assert '>1</span>' in count


def test_round_history_lives_in_the_stage_not_the_rail():
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
    assert 'data-ui="chat"' in board
    assert 'data-ui="round-history"' in board
    assert 'lg:max-h-[calc(100vh-7rem)]' in board
    assert 'lg:overflow-hidden' in board
    assert 'data-ui="alias-history"' not in board
    assert (board.index('data-ui="alias-teams"') < board.index('data-ui="chat"') < board.index('data-ui="alias-stage"')
            < board.index('data-ui="round-center"') < board.index('data-ui="round-history"'))
    assert board.count('data-ui="round-history"') == 1


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


def test_player_words_timer_ends_round_and_returns_word_to_pool() -> None:
    member = LobbyMember(user=User('timeout-writer', 'Writer'))
    team = Team(members=[member])
    game = GameState(config=GameConfig(player_words=True), state=StateMachine.ROUND_PLAYING,
                     teams={team.id: team}, active_team=team, active_player=member,
                     active_word='banana', word_pool=['apple'])
    lobby = Lobby(current_game=ALIAS, states={ALIAS: game}, members={member.uid: member})

    async def finish_timer() -> None:
        game.timer.finished = True

    game.timer.sleep = finish_timer
    asyncio.run(set_end_round_timer(lobby))

    assert game.state == StateMachine.REVIEWING
    assert game.active_word is None
    assert game.word_pool == ['apple', 'banana']
    assert game.guess_log == []


def test_player_words_can_keep_the_last_word_after_timeout() -> None:
    member = LobbyMember(user=User('last-word-writer', 'Writer'))
    team = Team(members=[member])
    game = GameState(config=GameConfig(player_words=True, player_words_last_word=True),
                     state=StateMachine.ROUND_PLAYING, teams={team.id: team},
                     active_team=team, active_player=member, active_word='banana')
    game.timer.set(game.config.time_limit)
    lobby = Lobby(current_game=ALIAS, states={ALIAS: game}, members={member.uid: member})

    async def finish_timer() -> None:
        game.timer.finished = True

    game.timer.sleep = finish_timer
    asyncio.run(set_end_round_timer(lobby))

    assert game.state == StateMachine.ROUND_PLAYING
    assert game.active_word == 'banana'
    assert 'data-phase="last-word"' in to_xml(WordPanel(member, game))


def test_player_words_keep_prefetched_word_in_first_word_round() -> None:
    member = LobbyMember(user=User('prefetched-writer', 'Writer'))
    team = Team(members=[member])
    game = GameState(config=GameConfig(player_words=True, player_words_last_word=True),
                     teams={team.id: team})
    game.start_game()
    game.submit_words(member, 'apple\npear')
    assert game.finish_word_collection()
    game.next_state()
    first_word = game.active_word
    remaining_word = (set(game.all_words) - {first_word}).pop()

    game.timer.finished = True
    assert not game.guess_word(member, True)
    assert game.active_word == remaining_word
    game.next_state()

    assert game.active_word is None
    assert game.word_pool == [remaining_word]
    game.next_state()
    assert game.state == StateMachine.VOTING_TO_START
    game.next_state()
    assert game.word_round == 1 and game.active_word == remaining_word
    assert game.guess_word(member, True)
    game.next_state()
    game.next_state()
    assert game.state == StateMachine.BETWEEN_WORD_ROUNDS


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
    assert 'hx-confirm' not in html
    assert 'data-uk-toggle="target: #alias-restart-confirm"' in html
    assert 'hx-post="/alias/restart_game"' in to_xml(RestartConfirmation())
    assert HostGameActions(guest, GameState()) is None


def test_player_written_words_block_wordpack_selection():
    host = LobbyMember(user=User('pack-host', 'Host'), is_host_=True)
    game = GameState(config=GameConfig(player_words=True))
    controls = to_xml(HostGameActions(host, game))
    random_pack = controls.split('Random wordpack')[0].rsplit('<button', 1)[-1]
    select = to_xml(PackSelectButton(game))
    board = to_xml(GameControls(host, game))

    assert 'disabled' in random_pack
    assert 'disabled' in select and 'data-uk-toggle' not in select
    assert 'Players write the words' in board and 'data-uk-toggle' not in board
    assert 'data-uk-toggle="target: #pack-select"' in to_xml(PackSelectButton(GameState()))


def test_wordpack_modal_refreshes_when_opened():
    html = to_xml(PackSelect(GameState()))

    assert 'hx-get="/alias/pack_select"' in html
    assert 'hx-trigger="shown"' in html


def test_alias_settings_only_save_from_the_update_button() -> None:
    host = LobbyMember(user=User('settings-host', 'Host'), is_host_=True)
    html = to_xml(ConfigLobby(host, GameState(config=GameConfig(player_words=True))))

    assert 'name="player_words"' in html
    assert 'name="player_words_last_word"' in html
    assert 'name="disable_skip"' in html
    assert html.count('hx-post="/alias/update_settings"') == 5
    assert 'name="player_words_last_word"' not in to_xml(ConfigLobby(host, GameState()))
    assert 'hx-trigger="change"' in html and 'hx-include="closest form"' in html
    assert 'mg-more-settings-body space-y-3 p-3 pt-2' in html


def test_one_team_rotates_leaders_and_shifts_guessers_each_circle():
    players = [LobbyMember(user=User(f'pair-{i}', f'Player {i}')) for i in range(4)]
    team = Team(members=players)
    game = GameState(config=GameConfig(wordpack=WordPack(words_='apple'), max_score=2),
                     teams={team.id: team})

    game.start_game()
    pairs = []

    for _ in range(8):
        pairs.append((game.active_player.uid, game.active_guesser.uid))
        game.next_state()  # start round
        game.guess_log = [GuessEntry('apple', 1)]
        game.next_state()  # review
        game.next_state()  # confirm review and advance

    assert pairs == [
        ('pair-0', 'pair-1'), ('pair-1', 'pair-2'), ('pair-2', 'pair-3'), ('pair-3', 'pair-0'),
        ('pair-0', 'pair-2'), ('pair-1', 'pair-3'), ('pair-2', 'pair-0'), ('pair-3', 'pair-1'),
    ]
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


def test_explainer_sees_their_guesser_name():
    explainer = LobbyMember(user=User('explainer', 'Alice'))
    guesser = LobbyMember(user=User('guesser', 'Bob'))
    team = Team(members=[explainer, guesser])
    game = GameState(state=StateMachine.ROUND_PLAYING, teams={team.id: team}, active_team=team,
                     active_player=explainer, active_guesser=guesser, active_word='apple')

    assert 'Explain to: Bob' in to_xml(CurrentWord(game))


def test_team_explainer_does_not_get_a_single_guesser():
    explainer = LobbyMember(user=User('team-explainer', 'Alice'))
    guesser = LobbyMember(user=User('team-guesser', 'Bob'))
    team = Team(members=[explainer, guesser])
    game = GameState(state=StateMachine.ROUND_PLAYING, active_team=team,
                     active_player=explainer, active_word='apple')

    assert 'Explain to:' not in to_xml(ExplainerPanel(explainer, game))


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


def test_player_words_finish_skipped_words_before_an_explicit_second_round():
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
    skipped = game.active_word
    assert not game.guess_word(player, False)
    assert game.active_word != skipped
    assert not game.guess_word(player, True)
    assert game.guess_word(player, True)
    game.next_state()
    game.next_state()
    assert game.state == StateMachine.BETWEEN_WORD_ROUNDS
    assert game.word_round == 1

    game.next_state()
    assert game.word_round == 2 and game.active_word in {'apple', 'pear'}
    assert not game.guess_word(player, True)
    assert game.guess_word(player, True)
    game.next_state()
    game.next_state()
    assert game.state == StateMachine.FINISHED


def test_second_word_round_skips_wait_for_the_next_explainer() -> None:
    players = [LobbyMember(user=User(f'skip-round-two-{i}', f'Player {i}')) for i in range(2)]
    team = Team(members=players)
    game = GameState(config=GameConfig(player_words=True), teams={team.id: team})
    game.start_game()
    game.start_word_round(['apple', 'pear'], round_number=2)
    game.state = StateMachine.VOTING_TO_START
    game.next_state()
    first_explainer = game.active_player

    assert not game.guess_word(first_explainer, False)
    assert game.guess_word(first_explainer, False)
    assert game.active_word is None
    assert set(game.skipped_words) == {'apple', 'pear'}
    game.next_state()
    game.next_state()
    assert game.state == StateMachine.VOTING_TO_START
    game.next_state()

    assert game.word_round == 2
    assert game.active_player != first_explainer
    assert game.active_word in {'apple', 'pear'}
    assert {game.active_word, *game.word_pool} == {'apple', 'pear'}
    assert not game.guess_word(game.active_player, True)
    assert game.guess_word(game.active_player, True)
    game.next_state()
    game.next_state()
    assert game.state == StateMachine.FINISHED


def test_player_word_submission_replaces_draft_and_locks_input() -> None:
    player = LobbyMember(user=User('autosave-writer', 'Writer'))
    team = Team(members=[player])
    game = GameState(state=StateMachine.COLLECTING_WORDS, teams={team.id: team})

    assert game.submit_words(player, 'apple\npear')
    assert game.submit_words(player, 'apple\nbanana')
    assert game.submitted_words[player.uid] == ['apple', 'banana']
    assert game.submit_words(player, 'apple\nbanana', finalized=True)
    assert not game.submit_words(player, 'changed later')

    game.timer.set(game.config.word_collection_time)
    html = to_xml(WordCollectionPanel(player, game))
    assert 'timer:expired from:#word-collection-timer' not in html
    assert 'Words submitted' in html
    assert 'readonly' in html and 'disabled' in html


def test_word_collection_autosubmits_at_timeout() -> None:
    player = LobbyMember(user=User('deadline-writer', 'Writer'))
    team = Team(members=[player])
    game = GameState(config=GameConfig(player_words=True), teams={team.id: team})
    game.start_game()
    lobby = Lobby(current_game=ALIAS, states={ALIAS: game}, members={player.uid: player})

    async def finish_timer() -> None:
        game.timer.finished = True

    async def submit_at_timeout() -> None:
        timer_task = asyncio.create_task(set_end_word_collection_timer(lobby))
        await asyncio.sleep(0)
        assert game.submit_words(player, 'apple\npear\nbanana', finalized=True)
        await timer_task

    game.timer.sleep = finish_timer
    asyncio.run(submit_at_timeout())

    assert game.state == StateMachine.VOTING_TO_START
    assert set(game.all_words) == {'apple', 'pear', 'banana'}
    assert set(game.word_pool) == set(game.all_words)


def test_word_collection_counts_locally_and_submits_on_timer() -> None:
    player = LobbyMember(user=User('local-count-writer', 'Writer'))
    game = GameState(state=StateMachine.COLLECTING_WORDS)
    game.timer.set(game.config.word_collection_time)

    html = to_xml(WordCollectionPanel(player, game))

    assert 'oninput=' in html and 'words entered' in html
    assert 'timer:expired from:#word-collection-timer' in html
    assert 'input changed delay:500ms' not in html


def test_hide_skipped_keeps_guesses_visible_and_skips_private():
    players = [LobbyMember(user=User(f'hide-{i}', f'P{i}')) for i in range(3)]
    team = Team(members=players)
    log = [GuessEntry('skipped-plum', 0, skipped=True), GuessEntry('guessed-plum', 1, skipped=False)]
    game = GameState(config=GameConfig(hide_skipped_words=True), state=StateMachine.ROUND_PLAYING,
                     teams={team.id: team}, active_team=team, active_player=players[0],
                     active_guesser=players[1], active_word='live-word', guess_log=log)
    game.timer.set(game.config.time_limit)
    lobby = Lobby(current_game=ALIAS, states={ALIAS: game}, members={p.uid: p for p in players})

    explainer = to_xml(Game(players[0], lobby))
    other = to_xml(Game(players[1], lobby))
    assert 'skipped-plum' in explainer and 'guessed-plum' in explainer and 'live-word' in explainer
    assert 'guessed-plum' in other and 'skipped-plum' not in other and 'live-word' not in other
    assert other.index('data-ui="alias-stage"') < other.index('guessed-plum')

    game.state = StateMachine.REVIEWING
    game.review_player = players[0]
    game.active_word = None
    review = to_xml(Game(players[2], lobby))
    assert 'guessed-plum' in review and 'skipped-plum' not in review
    assert 'skipped-plum' in to_xml(Game(players[0], lobby))


def test_player_words_hide_skips_from_everyone_except_the_explainer():
    explainer = LobbyMember(user=User('private-skip-explainer', 'Alice'))
    observer = LobbyMember(user=User('private-skip-observer', 'Bob'))
    team = Team(members=[explainer, observer])
    game = GameState(config=GameConfig(player_words=True), state=StateMachine.ROUND_PLAYING,
                     teams={team.id: team}, active_team=team, active_player=explainer,
                     guess_log=[GuessEntry('secret', 0, skipped=True), GuessEntry('visible', 1)])

    assert 'secret' in to_xml(RoundLog(explainer, game))
    observer_log = to_xml(RoundLog(observer, game))
    assert 'secret' not in observer_log
    assert 'visible' in observer_log


def test_player_words_force_hidden_skips_and_disable_skip_removes_action() -> None:
    member = LobbyMember(user=User('no-skip-writer', 'Writer'))
    team = Team(members=[member])
    game = GameState(config=GameConfig(player_words=True, disable_skip=True),
                     state=StateMachine.ROUND_PLAYING, teams={team.id: team},
                     active_team=team, active_player=member, active_word='apple')

    assert game.hides_skipped_words() and not game.config.hide_skipped_words
    assert not game.guess_word(member, False)
    assert game.active_word == 'apple' and game.guess_log == []
    assert '>Skip<' not in to_xml(ExplainerPanel(member, game))
    settings = to_xml(ConfigLobby(LobbyMember(user=User('no-skip-host', 'Host'), is_host_=True), game))
    box = settings[settings.rfind('<input', 0, settings.find('id="hide-skipped-words"')):settings.find('id="hide-skipped-words"')]
    assert 'checked' in box and 'disabled' in box
    assert 'name="hide_skipped_words"' not in settings


def test_round_break_is_ready_only_and_names_the_next_pair():
    explainer = LobbyMember(user=User('break-explainer', 'Alice'))
    guesser = LobbyMember(user=User('break-guesser', 'Bob'))
    team = Team(members=[explainer, guesser])
    game = GameState(config=GameConfig(player_words=True), state=StateMachine.BETWEEN_WORD_ROUNDS,
                     teams={team.id: team}, active_team=team, active_player=explainer, active_guesser=guesser)

    html = to_xml(GameControls(guesser, game))
    assert 'only one word' in html
    assert 'Alice is explaining' in html and 'Bob is guessing' in html
    assert "I'm ready" in html


def test_wordpack_picker_is_rendered_for_guests_with_disabled_selection():
    guest = LobbyMember(user=User('pack-guest', 'Guest'))
    html = to_xml(PackSelectContents(guest, GameState()))

    assert 'id="packs_select"' in html
    assert 'id="editor"' in html
    assert 'mg-pack-select-layout' in html
    assert 'mg-pack-select-list' in html and 'mg-pack-select-editor' in html
    assert 'Must be host to select' in html and 'disabled' in html


def _teams(*sizes: int, prefix: str) -> tuple[GameState, list[Team]]:
    teams = [Team(members=[LobbyMember(user=User(f'{prefix}-{t}-{i}', f'P{t}{i}')) for i in range(n)])
             for t, n in enumerate(sizes)]
    game = GameState(config=GameConfig(wordpack=WordPack(words_='apple\npear')), teams={t.id: t for t in teams})
    return game, teams


def _play_turn(game: GameState) -> None:
    game.next_state()  # start round
    game.next_state()  # review
    game.next_state()  # confirm


def test_member_who_joins_after_restart_gets_to_explain():
    game, (first, second) = _teams(2, 1, prefix='late')
    game.start_game()
    _play_turn(game)
    game.restart()
    late = LobbyMember(user=User('late-joiner', 'Late'))
    first.append(late)

    game.start_game()
    explainers = []
    for _ in range(6):
        explainers.append(game.active_player.uid)
        _play_turn(game)
    assert late.uid in explainers
    assert explainers[0] == first.members[0].uid


def test_teams_alternate_and_skip_a_team_that_left():
    game, (a, b, c) = _teams(1, 1, 1, prefix='order')
    game.start_game()
    assert game.active_team is a
    _play_turn(game)
    assert game.active_team is b
    game.remove_player(c.members[0].uid)
    _play_turn(game)
    assert game.active_team in (a, b) and c.id not in game.teams


def test_explainer_leaving_mid_round_moves_the_game_on():
    game, (team,) = _teams(3, prefix='leaver')
    game.start_game()
    game.next_state()
    leaver = game.active_player
    game.remove_player(leaver.uid)

    assert game.state == StateMachine.REVIEWING
    assert game.active_player != leaver and game.active_player in team


def test_wordpack_deck_reshuffles_instead_of_replaying_the_same_order():
    game, _ = _teams(1, prefix='deck')
    game.start_game()
    game.next_state()
    dealt = {game.active_word, game.next_word(), game.next_word()}
    assert dealt == {'apple', 'pear'}


def test_lobby_rules_are_shared_by_buttons_and_state():
    host = LobbyMember(user=User('rules-host', 'Host'), is_host_=True)
    game, _ = _teams(1, prefix='rules')
    game.config.max_teams = 1
    assert not game.can_add_team()
    lobby = Lobby(current_game=ALIAS, states={ALIAS: game}, members={host.uid: host})
    page = to_xml(Page(host, lobby))
    assert 'data-ui="new-team-card"' not in to_xml(Game(host, lobby))
    # the rules control has to sit above the settings or a tall host panel pushes it off screen
    assert page.find('>Rules<') != -1 and page.find('>Rules<') < page.find('Game settings')

    game.start_game()
    assert not game.can_change_wordpack()
    assert 'disabled' in to_xml(PackSelectButton(game))
    assert 'Game in progress' in to_xml(PackSelectContents(host, game))

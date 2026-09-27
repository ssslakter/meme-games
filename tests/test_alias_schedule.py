from meme_games.apps.alias.domain import GameState
from meme_games.apps.alias.domain.game import StateMachine
from meme_games.apps.alias.domain.team import Team
from meme_games.domain import LobbyMember, User


def make_game(n: int) -> GameState:
    game = GameState(state=StateMachine.ROUND_PLAYING)
    team = Team(members=[LobbyMember(user=User(f'u{i}', f'Player {i}')) for i in range(n)])
    game.teams[team.id] = team
    game.active_team = team
    return game


def turn_pairs(game: GameState, turns: int):
    game.set_pair()
    out = []
    for _ in range(turns):
        out.append(tuple(sorted((game.active_player.uid, game.active_guesser.uid))))
        game.advance_turn()
    return out


def leaders(game: GameState, turns: int):
    game.set_pair()
    out = []
    for _ in range(turns):
        out.append(game.active_player.uid)
        game.advance_turn()
    return out


def test_three_players_sit_at_most_one_round():
    game = make_game(3)
    pairs = turn_pairs(game, 12)
    uids = [m.uid for m in game.active_team.members]
    for i in range(len(pairs) - 2):
        active = set(pairs[i] + pairs[i+1] + pairs[i+2])
        assert active == set(uids), f'window {i}: {active}'


def test_each_player_explains_and_guesses_once_per_round():
    for n in (3, 4, 5):
        game = make_game(n)
        game.set_pair()
        uids = [m.uid for m in game.active_team.members]
        for _ in range(n - 1):
            explained, guessed = [], []
            for _turn in range(n):
                assert game.active_player.uid != game.active_guesser.uid
                explained.append(game.active_player.uid)
                guessed.append(game.active_guesser.uid)
                game.advance_turn()
            assert sorted(explained) == sorted(uids)
            assert sorted(guessed) == sorted(uids)


def test_three_players_roles_balance_over_two_cycles():
    game = make_game(3)
    lds = leaders(game, 12)
    for uid in [m.uid for m in game.active_team.members]:
        assert lds.count(uid) == 4, uid


def test_four_players_cover_all_pairs_and_swap_roles():
    game = make_game(4)
    uids = [m.uid for m in game.active_team.members]
    pairs = turn_pairs(game, 12)
    assert len({p for pair in pairs for p in pair}) == 4
    assert len(set(pairs)) == 6, f'all 6 pairs should appear: {set(pairs)}'
    lds = leaders(game, 12)
    for uid in uids:
        assert lds.count(uid) == 3, uid


def test_two_players_alternate_roles():
    game = make_game(2)
    lds = leaders(game, 4)
    assert lds == [lds[0], lds[1], lds[0], lds[1]] and lds[0] != lds[1]

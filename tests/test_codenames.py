from collections import Counter

from fasthtml.common import to_xml
from starlette.testclient import TestClient

from meme_games.apps.codenames.components.game import BoardCard
from meme_games.apps.codenames.domain import CardColor, CODENAMES, CodenamesState, GamePhase, TeamColor, WordCard
from meme_games.core import DI
from meme_games.domain import LobbyService
from meme_games.domain.user import UserManager
from meme_games.main import app
from meme_games.apps.word_packs.domain import WordPack


service = DI.get(LobbyService)
users = DI.get(UserManager)


def ready_lobby(lobby_id='codenames-rules'):
    people = [users.create(name=f'agent-{lobby_id}-{index}') for index in range(4)]
    lobby = service.create_lobby(people[0], lobby_id, CODENAMES)
    members = [lobby.host, *[lobby.create_member(user) for user in people[1:]]]
    state: CodenamesState = lobby.state
    for member, team in zip(members, [TeamColor.RED, TeamColor.RED, TeamColor.BLUE, TeamColor.BLUE]):
        member.play()
        assert state.join(member, team)
    assert state.toggle_spymaster(members[0])
    assert state.toggle_spymaster(members[2])
    return lobby, members, state


def test_start_builds_standard_board_and_role_requirements():
    _, members, state = ready_lobby('codenames-board')
    assert state.can_start()
    assert state.start()
    assert state.phase == GamePhase.CLUE
    assert len(state.board) == 25
    colors = Counter(card.color for card in state.board)
    assert colors[state.turn.card_color] == 9
    assert colors[state.turn.other.card_color] == 8
    assert colors[CardColor.NEUTRAL] == 7
    assert colors[CardColor.BOMB] == 1
    assert len({card.word.casefold() for card in state.board}) == 25
    assert not state.reveal(members[0], state.board[0].id), 'spymasters never guess'


def test_large_selected_wordpack_is_not_mixed_with_fallback_words():
    state = CodenamesState(wordpack=WordPack(name='Large', words_='\n'.join(f'custom-{n}' for n in range(30))))
    assert len(state._words()) == 30
    assert all(word.startswith('custom-') for word in state._words())


def test_clue_and_guess_advance_turn_without_leaking_roles():
    _, members, state = ready_lobby('codenames-turn')
    assert state.start()
    spymaster = members[0] if state.turn == TeamColor.RED else members[2]
    operative = members[1] if state.turn == TeamColor.RED else members[3]
    assert not state.give_clue(operative, 'signal', 2)
    assert not state.give_clue(spymaster, state.board[0].word, 2)
    assert not state.give_clue(spymaster, 'two words', 2)
    assert state.give_clue(spymaster, 'signal', 2)
    assert state.guesses_left == 3

    own = next(card for card in state.board if card.color == state.turn.card_color)
    operative_html = to_xml(BoardCard(operative, state, own))
    spymaster_html = to_xml(BoardCard(spymaster, state, own))
    assert 'data-color="hidden"' in operative_html
    assert f'data-color="{own.color.value}"' not in operative_html
    assert f'data-color="{own.color.value}"' in spymaster_html

    old_turn = state.turn
    neutral = next(card for card in state.board if card.color == CardColor.NEUTRAL)
    assert state.reveal(operative, neutral.id)
    assert neutral.revealed
    assert state.phase == GamePhase.CLUE
    assert state.turn == old_turn.other


def test_bomb_immediately_awards_the_other_team():
    _, members, state = ready_lobby('codenames-bomb')
    assert state.start()
    spymaster = members[0] if state.turn == TeamColor.RED else members[2]
    operative = members[1] if state.turn == TeamColor.RED else members[3]
    assert state.give_clue(spymaster, 'danger', 1)
    old_turn = state.turn
    bomb = next(card for card in state.board if card.color == CardColor.BOMB)
    assert state.reveal(operative, bomb.id)
    assert state.phase == GamePhase.FINISHED
    assert state.winner == old_turn.other


def test_codenames_page_is_live_and_uses_shared_lobby_shell():
    with TestClient(app, client=('10.0.1.30', 1), raise_server_exceptions=False) as client:
        page = client.get('/codenames/codenames-page', headers={'user-agent': 'Mozilla/5.0 Firefox'})
    assert page.status_code == 200
    assert 'data-page="codenames"' in page.text
    assert 'data-ui="game-shell"' in page.text
    assert 'data-ui="settings-panel"' in page.text
    assert 'under construction' not in page.text.lower()


def test_join_team_route_moves_member_out_of_spectators():
    lobby_id = 'codenames-http-join'
    with TestClient(app, client=('10.0.1.31', 1), raise_server_exceptions=False) as client:
        client.get(f'/codenames/{lobby_id}', headers={'user-agent': 'Mozilla/5.0 Firefox'})
        response = client.post('/codenames/join_team?team=red')
    lobby = service.lobbies[lobby_id]
    assert response.status_code == 200
    assert lobby.host.is_player
    assert lobby.state.team_of(lobby.host) == TeamColor.RED

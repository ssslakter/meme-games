"""Spectating is a lobby concept: it works the same whatever game is being played."""
import asyncio
from fasthtml.common import to_xml

from meme_games.core import DI
from meme_games.domain import LobbyService, BASIC_GAME
from meme_games.domain.user import UserManager
from meme_games.apps.shared.spectators import GAME_VIEWS, GameView, LobbyView, notify_roster_changed
from meme_games.apps.whoami.domain import WHOAMI
from meme_games.apps.alias.domain import ALIAS
import meme_games.main  # registers every game view

service = DI.get(LobbyService)
um = DI.get(UserManager)


def _lobby(id, game):
    host = um.create(name=f'host-{id}')
    lobby = service.create_lobby(host, id, game)
    return lobby, lobby.get_member(host.uid)


def test_games_with_a_board_register_a_view():
    assert set(GAME_VIEWS) >= {WHOAMI, ALIAS}


def test_lobby_without_a_game_view_renders_nothing():
    lobby, _ = _lobby('spec1', BASIC_GAME)
    assert GameView(lobby.host, lobby) is None


def test_spectating_works_without_a_game_view():
    lobby, m = _lobby('spec2', BASIC_GAME)
    m.play()
    service.spectate(m, lobby)
    assert not m.is_player
    asyncio.run(notify_roster_changed(lobby))  # no connected members, must not raise


def test_spectating_removes_the_player_from_the_game():
    lobby, m = _lobby('spec3', ALIAS)
    m.play()
    team = lobby.state.create_team()
    team.append(m)
    lobby.state.add_vote(m)

    service.spectate(m, lobby)

    assert not m.is_player
    assert m.uid not in lobby.state.votes
    assert not lobby.state.team_by_player(m)


def test_lobby_view_lists_spectators_and_the_board():
    lobby, m = _lobby('spec4', WHOAMI)
    m.play()
    other = um.create(name='watcher')
    lobby.create_member(other)  # joins as a spectator

    html = to_xml(LobbyView(m, lobby))
    assert 'id="spectators"' in html
    assert 'watcher' in html
    assert 'id="game"' in html

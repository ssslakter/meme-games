"""One lobby, many games: switching keeps the members and each game's state."""
from meme_games.core import DI
from meme_games.services import db
from meme_games.domain import LobbyService, BASIC_GAME, GAME_REGISTRY
from meme_games.domain.user import UserManager
from meme_games.apps.whoami.domain import WHOAMI, WhoAmIState
from meme_games.apps.alias.domain import ALIAS

service = DI.get(LobbyService)
host = DI.get(UserManager).create(name='switcher')


def test_switching_game_keeps_members_and_state():
    lobby = service.create_lobby(host, 'switch1', WHOAMI, persistent=True)
    uid = host.uid
    lobby.state.player(uid).set_notes('remember me')

    lobby.play_game(ALIAS)
    assert lobby.current_game == ALIAS
    assert uid in lobby.members, 'switching a game must not drop members'
    assert lobby.state.teams == {}, 'alias starts with its own empty state'

    lobby.play_game(WHOAMI)
    assert lobby.state.player(uid).notes == 'remember me'


def test_persisted_state_survives_eviction():
    lobby = service.create_lobby(host, 'switch2', WHOAMI, persistent=True)
    lobby.get_member(host.uid).play()
    lobby.state.player(host.uid).set_label('a label')
    service.update(lobby)

    service.evict_lobby('switch2')
    assert 'switch2' not in service.lobbies

    reloaded = service.get_lobby('switch2')
    assert reloaded.current_game == WHOAMI
    assert reloaded.state.player(host.uid).label_text == 'a label'


def test_only_persistent_games_are_written():
    lobby = service.create_lobby(host, 'switch3', ALIAS, persistent=True)
    assert not GAME_REGISTRY[ALIAS].persist
    assert lobby.dump_states() == '', 'alias state holds live timers and iterators, never the db'


def test_plain_lobby_has_no_state():
    lobby = service.create_lobby(host, 'switch4', BASIC_GAME)
    assert lobby.state is None
    service.spectate(lobby.get_member(host.uid), lobby)  # must not blow up without a state


def test_removing_a_member_clears_them_from_every_game():
    lobby = service.create_lobby(host, 'switch5', WHOAMI)
    lobby.state.player(host.uid).set_notes('gone soon')
    lobby.play_game(ALIAS)
    team = lobby.state.create_team()
    team.append(lobby.get_member(host.uid))
    lobby.state.add_vote(lobby.get_member(host.uid))

    lobby.remove_member(host.uid)

    assert host.uid not in lobby.states[WHOAMI].players
    assert host.uid not in lobby.states[ALIAS].votes


def test_alias_removes_all_duplicate_team_memberships():
    lobby = service.create_lobby(host, 'switch6', ALIAS)
    member = lobby.get_member(host.uid)
    first, second = lobby.state.create_team(), lobby.state.create_team()
    first.append(member)
    second.append(member)

    lobby.state.remove_player(member.uid)

    assert all(member not in team for team in lobby.state.teams.values())


def test_stale_websocket_cannot_disconnect_the_new_connection():
    lobby = service.create_lobby(host, 'switch7', WHOAMI)
    member = lobby.get_member(host.uid)
    old_ws, new_ws = object(), object()
    member.connect(lambda _: None, old_ws)
    member.connect(lambda _: None, new_ws)

    member.disconnect(old_ws)

    assert member.ws is new_ws

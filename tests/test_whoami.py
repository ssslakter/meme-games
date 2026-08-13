"""The Who Am I board: what each player is allowed to see, and what survives a restart."""
from fasthtml.common import to_xml

from meme_games.apps.whoami.components.cards import PlayerCard, PlayerLabelText
from meme_games.apps.whoami.components.notes import NotesCard
from meme_games.apps.whoami.domain import WHOAMI, WhoAmIState
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

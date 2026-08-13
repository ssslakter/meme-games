from ...shared import *
from ...shared.settings import Setting
from ..domain import *
from meme_games.domain import Lobby, LobbyMember, User, is_host


def PrivateNotesSetting(lobby: Lobby):
    from ..routes import toggle_private_notes
    private = lobby.state.config.private_notes
    args = ('eye-off', 'Notes: private') if private else ('eye', 'Notes: shared')
    return Setting(*args, hx_post=toggle_private_notes)(hx_swap_oob='outerHTML', id='private-notes-setting')


def WhoAmISettings(reciever: LobbyMember | User, lobby: Lobby):
    if not is_host(reciever): return None
    return PrivateNotesSetting(lobby)

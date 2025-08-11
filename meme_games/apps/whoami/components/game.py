from ...shared.spectators import Spectators
from ...shared import *
from ...shared.settings import LockLobby
from ...user import *
from ..domain import *
from .cards import *
from .notes import *

def Game(reciever: WhoAmIPlayer | User, lobby: Lobby):
    new_player = [] if is_player(reciever) else [NewPlayerCard()]
    player_classes = "pt-20 flex flex-row justify-center flex-wrap gap-8"
    return Div(
        Div(
            *[PlayerCard(reciever, p, lobby) for p in lobby.sorted_members()]
            + new_player,
            id="players",
            cls=player_classes,
        ),
        NotesBlock(reciever),
    )


def MainBlock(reciever: WhoAmIPlayer | User, lobby: Lobby):
    from ..routes import ws_url
    from ..monitor import monitor

    return LobbyPage(
        Game(reciever, lobby),
        SettingsPopover(LockLobby(lobby) if is_host(reciever) else None),
        Spectators(reciever, lobby),
        navbar_args=[A("Monitor", href=monitor.to(), cls=AT.text)],
        hx_ext="ws",
        ws_connect=ws_url,
        background_url=lobby.background_url,
        _="on htmx:wsBeforeMessage call sendWSEvent(event)",
    )

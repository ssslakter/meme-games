from ...shared import *
from ..domain import *
from .cards import *
from .notes import *


def Spectators(reciever: WhoAmIPlayer | User, lobby: Lobby):
    from ..routes import spectate

    panel_classes = "bg-white/60 dark:bg-gray-900/60"
    spectator_classes = (
        "fixed right-0 top-1/2 -translate-y-1/2 "
        "flex flex-col p-2 gap-1 rounded-l-lg shadow-lg "
        "focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
    )
    spectate_controls = dict(
        hx_post=spectate,
        hx_swap="beforeend",
        hx_target="#players",
        cls=f"{panel_classes} {spectator_classes} cursor-pointer",
        tabindex="0",
    )

    inner_div_classes = "flex flex-col gap-1"

    return Panel(
        "Spectators: ",
        Div(
            *[
                UserName(reciever, p.user, is_connected=p.is_connected)
                for p in lobby.sorted_members()
                if not p.is_player
            ],
            id="spectators",
            cls=inner_div_classes,
        ),
        rounded='0',
        **spectate_controls,
    )


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

    return MainPage(
        Game(reciever, lobby),
        SettingsPopover(reciever, lobby),
        Spectators(reciever, lobby),
        navbar_args=[A("Monitor", href=monitor.to())],
        hx_ext="ws",
        ws_connect=ws_url,
        background_url=lobby.background_url,
        _="on htmx:wsBeforeMessage call sendWSEvent(event)",
    )


def JoinSpectators(r: WhoAmIPlayer, p: WhoAmIPlayer):
    return Div(UserName(r.user, p.user), hx_swap_oob="beforeend:#spectators")


def ActiveGameState(r: WhoAmIPlayer | User, lobby: Lobby):
    return Spectators(r, lobby), Game(r, lobby)

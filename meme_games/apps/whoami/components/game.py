from ...shared import *
from ..domain import *
from .cards import *
from .notes import *


def Background(url: str):
    """
    Creates a background div with the given image url and styles it with tailwind classes.
    """
    url = url or "/media/background.jpg"
    classes = "absolute top-0 left-0 -z-10 h-full w-full bg-black bg-cover bg-center bg-no-repeat blur-[5px] brightness-50"
    return Div(style=f"background-image: url('{url}')", cls=classes)


def Spectators(reciever: WhoAmIPlayer | User, lobby: Lobby):
    from ..routes import spectate

    panel_classes = "bg-white/60 dark:bg-gray-900/60"
    spectator_classes = (
        "fixed right-0 top-1/2 -translate-y-1/2 "
        "flex flex-col p-2 gap-1 rounded-l-lg shadow-lg"
    )
    spectate_controls = dict(
        hx_post=spectate,
        hx_swap="beforeend",
        hx_target="#players",
        cls=f"{panel_classes} {spectator_classes} cursor-pointer",
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

    return MainPage(
        Spectators(reciever, lobby),
        Game(reciever, lobby),
        SettingsPopover(reciever, lobby),
        hx_ext="ws",
        ws_connect=ws_url,
        background_url=lobby.background_url,
        _="on htmx:wsBeforeMessage call sendWSEvent(event)",
    )


def JoinSpectators(r: WhoAmIPlayer, p: WhoAmIPlayer):
    return Div(UserName(r.user, p.user), hx_swap_oob="beforeend:#spectators")


def ActiveGameState(r: WhoAmIPlayer | User, lobby: Lobby):
    return Spectators(r, lobby), Game(r, lobby)

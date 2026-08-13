from meme_games.core import *
from meme_games.domain import LobbyMember, User, Lobby, LobbyService
from meme_games.domain.notify import notify_all
from meme_games.apps.user.components import MemberName
from ..shared.utils import register_route, lobby_state


rt = APIRouter('/lobby')
register_route(rt)


GAME_VIEWS: dict[str, Callable[[LobbyMember | User, Lobby], Any]] = {}

def register_game_view(game: str, view_fn: Callable[[LobbyMember | User, Lobby], Any]):
    '''How to re-render `game`'s board for one member. Lobbies without a board
    (video) simply do not register one.'''
    GAME_VIEWS[game] = view_fn


def GameView(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    view = GAME_VIEWS.get(lobby.current_game)
    return view(reciever, lobby, **kwargs) if view else None


def SpectatorsList(reciever: LobbyMember | User, lobby: Lobby):
    return Div(
            *[
                MemberName(reciever, p)
                for p in lobby.sorted_members()
                if not p.is_player
            ],
            id="spectators",
            cls="mg-spectators-list flex flex-col gap-1", data_ui='spectators-list',
        )

def Spectators(reciever: LobbyMember | User, lobby: Lobby, cls = 'right-0 top-1/3 -translate-y-1/2'):
    return Card(
        "Spectators: ",
        SpectatorsList(reciever, lobby),
        body_cls='p-2',
        hx_post=spectate,
        hx_swap='none',
        tabindex="0",
        cls=f"mg-spectators fixed rounded-r-none p-2 cursor-pointer {cls}",
        data_ui='spectators'
    )


def LobbyView(reciever: LobbyMember | User, lobby: Lobby):
    '''Everything that changes when the player/spectator split changes.'''
    return SpectatorsList(reciever, lobby), GameView(reciever, lobby, hx_swap_oob='true')


async def notify_roster_changed(lobby: Lobby):
    '''Tell everyone the players and spectators changed.'''
    await notify_all(lobby, lambda r, *_: LobbyView(r, lobby))


@rt
async def spectate(req: Request):
    lobby, _, p = lobby_state(req)
    if not p.is_player: return
    if lobby.locked: return add_toast(req.session, "Game is locked", "error")
    DI.get(LobbyService).spectate(p, lobby)
    await notify_roster_changed(lobby)

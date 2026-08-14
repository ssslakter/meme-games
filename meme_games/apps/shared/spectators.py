from meme_games.core import *
from meme_games.domain import LobbyMember, User, Lobby, LobbyService, LobbyChanged, lobby_events
from meme_games.domain.notify import notify_all
from meme_games.apps.user.components import MemberName, UserInfo
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
    watching = [p for p in lobby.sorted_members() if not p.is_player]
    return Div(
            *[UserInfo(reciever, p.user, is_connected=p.is_connected, is_host=p.is_host, avatar_cls='h-7 w-7')
              for p in watching],
            P('Nobody is watching yet.', cls=(TextT.muted, TextT.sm, 'm-0'))
            if not watching else None,
            id="spectators",
            cls="mg-spectators-list flex flex-col gap-2", data_ui='spectators-list',
        )

def Spectators(reciever: LobbyMember | User, lobby: Lobby, cls='', **kwargs):
    watching = sum(not p.is_player for p in lobby.members.values())
    return Card(
        Div(
            DivLAligned(
                UkIcon('eye', width=18, height=18, cls='shrink-0'),
                H5('Spectators', cls='m-0'),
                Span(watching, cls='mg-spectators-count rounded-full bg-secondary px-2 py-0.5 text-xs'),
                cls='gap-2'),
            Button(UkIcon('eye', cls='mr-1', width=16, height=16), 'Watch',
                   hx_post=spectate, hx_swap='none', title='Leave the game and watch',
                   cls=(ButtonT.default, 'shrink-0 whitespace-nowrap px-3 py-1 text-sm'))
            if isinstance(reciever, LobbyMember) and reciever.is_player else None,
            cls='flex items-center justify-between gap-3'),
        SpectatorsList(reciever, lobby),
        body_cls='space-y-3 p-4',
        id='spectators-panel', cls=f"mg-spectators w-full min-w-0 {cls}",
        data_ui='spectators', **kwargs
    )


def LobbyView(reciever: LobbyMember | User, lobby: Lobby):
    '''Everything that changes when the player/spectator split changes.'''
    return Spectators(reciever, lobby, hx_swap_oob='true'), GameView(reciever, lobby, hx_swap_oob='true')


async def notify_roster_changed(lobby: Lobby):
    '''Tell everyone the players and spectators changed.'''
    await lobby_events.publish(lobby, 'roster')


async def _render_roster_event(event: LobbyChanged, lobby: Lobby):
    if 'roster' in event.topics:
        await notify_all(lobby, lambda r, *_: LobbyView(r, lobby))


lobby_events.subscribe(_render_roster_event)


@rt
async def spectate(req: Request):
    lobby, _, p = lobby_state(req)
    if not p.is_player: return
    if lobby.locked: return add_toast(req.session, "Game is locked", "error")
    DI.get(LobbyService).spectate(p, lobby)
    await notify_roster_changed(lobby)

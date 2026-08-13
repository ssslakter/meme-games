from ...shared import *
from ...shared.settings import LockLobby
from ...user import *
from ..domain import *
from .cards import *
from .notes import *
from .settings import *


def BoardTransform():
    '''One outbound websocket channel for every drag on the board.'''
    return Div(id='board-transport', cls='hidden', ws_send=True, hx_trigger='board-move',
               hx_vals='js:{...(window.mgBoardMsg || {})}')


def Game(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    players = [p for p in lobby.sorted_members() if p.is_player]
    cards = [PlayerCard(reciever, p, lobby, i) for i, p in enumerate(players)]
    if not is_player(reciever): cards.append(NewPlayerCard(len(players)))
    return Div(
        Div(*cards, id='players', cls='mg-board', data_ui='board',
            style=f'height:{board_height(len(cards))}px'),
        BoardTransform(),
        id='game',
        cls=stringify(('mg-game mg-game-whoami', kwargs.pop('cls', ''))),
        data_ui='game', data_game='whoami',
        **kwargs
    )


def MainBlock(reciever: LobbyMember | User, lobby: Lobby):
    from ..routes import ws_url
    from ..monitor import monitor

    return LobbyPage(
        GameShell(
            Game(reciever, lobby),
            LobbyTools(reciever, lobby, WhoAmISettings(reciever, lobby),
                       LockLobby(lobby) if is_host(reciever) else None)),
        navbar_args=[A("Monitor", href=monitor.to(), cls=AT.text)],
        hx_ext="ws",
        ws_connect=ws_url,
        user=reciever,
        page='whoami',
        _="on htmx:wsBeforeMessage call onBoardMessage(event)",
    )

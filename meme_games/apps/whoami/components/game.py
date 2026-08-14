from ...shared import *
from ...user import *
from ..domain import *
from .cards import *
from .notes import *
from .settings import *


def BoardTransform():
    '''One outbound websocket channel for every drag on the board.'''
    return Div(id='board-transport', cls='hidden', ws_send=True, hx_trigger='board-move',
               hx_vals='js:{...(window.mgBoardMsg || {})}')


def TopicBanner(lobby: Lobby, **kwargs):
    return H2(lobby.state.config.topic.strip() or 'Everything', id='whoami-topic',
              cls='mg-whoami-topic m-0 text-center', **kwargs)


def TurnStatus(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    from ..routes import end_turn
    state: WhoAmIState = lobby.state
    active = lobby.members.get(state.current_turn_uid)
    return Div(
        P(f"{active.name}'s turn" if active else 'Set a card for every player, then start.',
          cls='m-0 font-medium'),
        Button('End turn', hx_post=end_turn, hx_swap='none', cls=(ButtonT.primary, 'px-4 py-2'))
            if active and isinstance(reciever, LobbyMember) and reciever == active and active.user.kind != 'agent'
            else None,
        id='whoami-turn', cls='flex items-center justify-center gap-4', **kwargs)


def QuestionUpdates(reciever, lobby):
    return tuple(QuestionPanel(reciever, player, lobby, hx_swap_oob='outerHTML')
                 for player in lobby.sorted_members() if player.is_player)


def Game(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    players = [p for p in lobby.sorted_members() if p.is_player]
    cards = [PlayerCard(reciever, player, lobby) for player in players]
    if not is_player(reciever) and not lobby.locked: cards.append(NewPlayerCard())
    return Div(
        Div(TopicBanner(lobby), TurnStatus(reciever, lobby),
            cls='mg-whoami-header space-y-1'),
        Div(*cards, id='players', cls='mg-board', data_ui='board'),
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
            LobbyTools(reciever, lobby, WhoAmISettings(reciever, lobby))),
        NotesBlock(reciever, lobby),
        navbar_args=[A("Monitor", href=monitor.to(), cls=AT.text)],
        hx_ext="ws",
        ws_connect=ws_url,
        user=reciever,
        page='whoami',
        _="on htmx:wsBeforeMessage call onBoardMessage(event)",
    )

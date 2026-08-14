from ...shared import *
from meme_games.apps.user import *
from meme_games.domain import Lobby, LobbyMember, User, is_player
from ..domain import *
from .notes import *
from .basic import *


def PlayerLabelText(r: LobbyMember | User, owner: LobbyMember, data: PlayerNotes, lobby: Lobby = None):
    '''The owner sees only a marker; their previous player edits; everyone else reads.'''
    tfm = data.label_tfm or default_label_tfm()
    style = f'width:{tfm.width}px; height:{tfm.height}px;'
    if r.uid == owner.uid:
        return (TextArea(readonly=True, style=style, cls='mg-label-input'),
                Div('?' if data.label_text else '', cls='mg-label-hidden', data_label_text=owner.uid))
    order = ([p.uid for p in lobby.sorted_members() if p.is_player]
             if lobby and lobby.state.phase == WhoAmIPhase.WAITING else lobby.state.turn_order if lobby else [])
    author = lobby.state.previous_player(owner.uid, order) if lobby else None
    editable = isinstance(r, LobbyMember) and r.uid == author
    return TextArea(data.label_text, placeholder='enter label' if editable else '', name='label', maxlength=CARD_MAX,
                    style=style, cls='mg-label-input', readonly=not editable,
                    ws_send=True if editable else None,
                    hx_trigger='input changed delay:100ms' if editable else None,
                    hx_vals={'owner_uid': owner.uid, 'type': 'label_text'} if editable else None,
                    data_label_text=owner.uid)


def PlayerLabelFT(r: LobbyMember | User, owner: LobbyMember, data: PlayerNotes, lobby: Lobby):
    tfm = data.label_tfm or default_label_tfm()
    return Div(
        Div(cls='mg-label-handle', title='Drag to move'),
        PlayerLabelText(r, owner, data, lobby),
        style=f'left:{tfm.x}px; top:{tfm.y}px;',
        cls='mg-label', data_label=owner.uid, data_drag='label', data_uid=owner.uid,
    )


def GuessedToggle(reciever: LobbyMember | User, owner: LobbyMember, data: PlayerNotes, state: WhoAmIState):
    '''Marks a player as done, so the turn order stops stopping at them.'''
    from ..routes import set_guessed
    if state.phase != WhoAmIPhase.PLAYING: return None
    label = 'Guessed ✓' if data.guessed else 'Mark as guessed'
    return Div(
        Button(label, hx_post=set_guessed.to(uid=owner.uid, guessed=not data.guessed), hx_swap='none',
               disabled=not is_player(reciever),
               cls=('uk-btn', ButtonT.default, 'mg-guessed-btn w-full px-2 py-1 text-xs')),
        cls='mg-card-actions', data_nodrag='true')


def PlayerCard(reciever: LobbyMember | User, p: LobbyMember, lobby: Lobby):
    if not p.is_player: return
    state: WhoAmIState = lobby.state
    data = state.player(p.uid)
    return PlayerCardBase(
        Div(AvatarBig(p.user, cls='h-full w-full bg-cover bg-center bg-no-repeat dark:brightness-75'),
            cls='mg-card-face'),
        Div(MemberName(reciever, p), cls='mg-card-name'),
        GuessedToggle(reciever, p, data, state),
        PlayerLabelFT(reciever, p, data, lobby),
        QuestionPanel(reciever, p, lobby),
        SharedNotesCard(reciever, p, data, state),
        style=f'width:{CARD_W}px; height:{CARD_H}px;', data_card=p.uid,
        data_guessed='true' if data.guessed else 'false',
    )


def NewPlayerCard():
    from ..routes import play
    return PlayerCardBase(
        Div('+', cls='mg-new-player-icon'),
        Div('Join the game', cls='mg-card-name'),
        style=f'width:{CARD_W}px; height:{CARD_H}px;',
        cls='mg-new-player cursor-pointer',
        id='new-player-card',
        hx_post=play,
        hx_swap='none',  # the websocket board re-render replaces this card
    )

from ...shared import *
from meme_games.apps.user import *
from ..domain import *
from .notes import *
from .basic import *


def PlayerLabelText(r: LobbyMember | User, owner: LobbyMember, data: PlayerNotes):
    '''Everyone but the owner reads and edits the label; the owner only sees that one exists.'''
    tfm = data.label_tfm or default_label_tfm()
    style = f'width:{tfm.width}px; height:{tfm.height}px;'
    if r.uid == owner.uid:
        return (TextArea(readonly=True, style=style, cls='mg-label-input'),
                Div('?' if data.label_text else '', cls='mg-label-hidden', data_label_text=owner.uid))
    return TextArea(
        data.label_text, placeholder='enter label', name='label', style=style, cls='mg-label-input',
        ws_send=True, hx_trigger='input changed delay:100ms',
        hx_vals={'owner_uid': owner.uid, 'type': 'label_text'},
        data_label_text=owner.uid,
    )


def PlayerLabelFT(r: LobbyMember | User, owner: LobbyMember, data: PlayerNotes):
    tfm = data.label_tfm or default_label_tfm()
    return Div(
        Div(cls='mg-label-handle', title='Drag to move'),
        PlayerLabelText(r, owner, data),
        style=f'left:{tfm.x}px; top:{tfm.y}px;',
        cls='mg-label', data_label=owner.uid, data_drag='label', data_uid=owner.uid,
    )


def PlayerCard(reciever: LobbyMember | User, p: LobbyMember, lobby: Lobby, index: int = 0):
    if not p.is_player: return
    state: WhoAmIState = lobby.state
    data = state.player(p.uid)
    pos = data.card_pos or default_card_pos(index)
    return PlayerCardBase(
        Div(AvatarBig(p.user, cls='h-full w-full bg-cover bg-center bg-no-repeat dark:brightness-75'),
            cls='mg-card-face'),
        Div(MemberName(reciever, p), ' ✪' if lobby.host == p else None, cls='mg-card-name'),
        PlayerLabelFT(reciever, p, data),
        NotesCard(reciever, p, data, state),
        style=f'left:{pos.x}px; top:{pos.y}px; width:{CARD_W}px; height:{CARD_H}px;',
        data_drag='card', data_uid=p.uid, data_card=p.uid,
    )


def NewPlayerCard(index: int = 0):
    from ..routes import play
    pos = default_card_pos(index)
    return PlayerCardBase(
        Div('+', cls='mg-new-player-icon'),
        Div('Join the game', cls='mg-card-name'),
        style=f'left:{pos.x}px; top:{pos.y}px; width:{CARD_W}px; height:{CARD_H}px;',
        cls='mg-new-player cursor-pointer',
        id='new-player-card',
        hx_post=play,
        hx_swap='outerHTML',
    )

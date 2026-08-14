from ...shared import *
from meme_games.domain import LobbyMember, User
from ..domain import PlayerLabel, WhoAmIState

CARD_W, CARD_H = 280, 300
LABEL_W, LABEL_H = 160, 84
NOTES_W, NOTES_H = 280, 180


def default_label_tfm() -> PlayerLabel:
    return PlayerLabel(x=(CARD_W - LABEL_W) // 2, y=16, width=LABEL_W, height=LABEL_H)


def notes_visible(reciever: LobbyMember | User, owner: LobbyMember, state: WhoAmIState) -> bool:
    '''Your own notes are always yours to see; everyone else's depend on the lobby setting.'''
    return reciever == owner or not state.config.private_notes


def PlayerCardBase(*args, cls=(), **kwargs):
    return Div(*args,
               cls=stringify(('mg-game-card mg-player-card group relative', cls)),
               data_ui='player-card',
               **kwargs)

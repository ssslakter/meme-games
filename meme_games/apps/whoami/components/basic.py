from ...shared import *
from meme_games.domain import LobbyMember, User
from ..domain import CardPos, PlayerLabel, PlayerNotes, WhoAmIState

CARD_W, CARD_H = 280, 300
LABEL_W, LABEL_H = 160, 84
NOTES_W, NOTES_H = 280, 64

BOARD_COLS = 3
COL_PITCH, ROW_PITCH = CARD_W + 32, CARD_H + NOTES_H + 96
PAD_X, PAD_Y = 16, 96


def default_card_pos(index: int) -> CardPos:
    '''Cards nobody has moved yet are dealt into a grid.'''
    col, row = index % BOARD_COLS, index // BOARD_COLS
    return CardPos(x=PAD_X + col * COL_PITCH, y=PAD_Y + row * ROW_PITCH)


def default_label_tfm() -> PlayerLabel:
    '''Above the card, so a fresh label never covers the avatar.'''
    return PlayerLabel(x=(CARD_W - LABEL_W) // 2, y=-(LABEL_H + 16), width=LABEL_W, height=LABEL_H)


def board_height(card_count: int) -> int:
    '''Tall enough for the dealt rows; CSS keeps it at least a screen tall.'''
    rows = max(1, -(-card_count // BOARD_COLS))
    return PAD_Y + rows * ROW_PITCH


def notes_visible(reciever: LobbyMember | User, owner: LobbyMember, state: WhoAmIState) -> bool:
    '''Your own notes are always yours to see; everyone else's depend on the lobby setting.'''
    return reciever == owner or not state.config.private_notes


def PlayerCardBase(*args, cls=(), **kwargs):
    '''A plain div, not a Card: the label and notes hang outside its bounds.'''
    return Div(*args,
               cls=stringify(('mg-game-card mg-player-card group absolute', cls)),
               data_ui='player-card',
               **kwargs)

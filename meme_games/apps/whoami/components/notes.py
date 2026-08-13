from ...shared import *
from ...user import *
from ..domain import *
from meme_games.domain import User, LobbyMember
from .basic import *


def NotesCard(reciever: LobbyMember | User, owner: LobbyMember, data: PlayerNotes, state: WhoAmIState):
    '''A fixed-size pad clipped to the card; hovering it lifts the pad to show the whole note.'''
    from ..routes import notes
    if not notes_visible(reciever, owner, state): return None
    own = reciever == owner
    body = (TextArea(data.notes, name='text', placeholder='Your notes', cls='mg-notes-input',
                     hx_post=notes, hx_trigger='input changed delay:500ms', hx_swap='none')
            if own else
            Div(data.notes, cls='mg-notes-text'))
    return Div(
        Div('Notes' if own else Span(MemberName(reciever, owner), "'s notes"), cls='mg-notes-title'),
        body,
        style=f'top:{CARD_H + 8}px; width:{NOTES_W}px; height:{NOTES_H}px;',
        cls='mg-notes', data_notes=owner.uid, data_ui='player-notes', data_nodrag='true',
    )

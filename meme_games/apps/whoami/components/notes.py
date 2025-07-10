from ...shared import *
from ..domain import *
from .basic import *

def Notes(reciever: WhoAmIPlayer | User, author: WhoAmIPlayer, cls=(), **kwargs):
    from ..routes import notes
    textarea_classes = 'w-[300px] h-[300px] resize overflow-auto p-1 rounded-lg block'
    notes_kwargs = (dict(hx_post=notes,
                         hx_trigger="input changed delay:500ms, load",
                         hx_swap='none',
                         placeholder="Your notes")
                    if reciever == author
                    else dict(readonly=True,
                              data_notes=author.uid)
                    )

    return mui.Card(TextArea(author.notes, name='text', cls=textarea_classes, **notes_kwargs), cls=('z-50', stringify(cls)), **kwargs)


def NotesBlock(r: WhoAmIPlayer | User):
    return Div(Notes(r, r, cls='draggable-panel fixed left-1/2 top-1/2 -translate-x-1/2 p-4') if is_player(r) else None, 
               id='notes-block', hx_swap_oob='true', cls='m-5')

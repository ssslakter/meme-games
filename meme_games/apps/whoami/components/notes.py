from ...shared import *
from ..domain import *
from meme_games.domain import User, is_player
from .basic import *

def Notes(reciever: WhoAmIPlayer | User, author: WhoAmIPlayer, cls=(), text_cls='', text_kwargs = None, **kwargs):
    from ..routes import notes
    textarea_classes = f'shadow-none overflow-auto p-1 {text_cls}'
    notes_kwargs = (dict(hx_post=notes,
                         hx_trigger="input changed delay:500ms, load",
                         hx_swap='none',
                         placeholder="Your notes")
                    if reciever == author
                    else dict(readonly=True)
                    )
    if text_kwargs: notes_kwargs = {**notes_kwargs, **text_kwargs} 

    return Card(TextArea(author.notes, name='text', cls=textarea_classes, **notes_kwargs),
                cls=('z-50 flex flex-col', stringify(cls)), 
                body_cls='p-0 flex flex-col h-full',
                data_notes=author.uid,
                **kwargs)


def NotesBlock(r: WhoAmIPlayer | User):
    return Div(Notes(r, r, text_cls='resize', text_kwargs={'rows':12, 'cols':25},
                     cls='draggable-panel fixed left-1/2 top-1/2 -translate-x-1/2 p-3') if is_player(r) else None, 
               id='notes-block', hx_swap_oob='true', cls='m-5')

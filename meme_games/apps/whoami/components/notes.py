from meme_games.core import *
from meme_games.domain import *
from ...shared import *
from ..domain import *

def Notes(reciever: WhoAmIPlayer | User, author: WhoAmIPlayer, **kwargs):
    from ..routes import notes
    notes_base_classes = 'w-[var(--card-width)] h-[var(--card-height)] text-2xl p-2 scrollbar-hide outline-none'
    notes_kwargs = (dict(hx_post=notes,
                         hx_trigger="input changed delay:500ms, load",
                         hx_swap='none',
                         placeholder="Your notes")
                    if reciever == author
                    else dict(readonly=True,
                              data_notes=author.uid)
                    )

    return Panel(Textarea(author.notes, name='text', cls=(notes_base_classes, kwargs.pop('cls', '')), **notes_kwargs, **kwargs))


def NotesBlock(r: WhoAmIPlayer | User):
    return Div(Notes(r, r) if is_player(r) else None, id='notes-block', hx_swap_oob='true')

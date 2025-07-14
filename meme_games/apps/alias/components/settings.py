from meme_games.core import *
from meme_games.apps.word_packs.components import *

def PackSelect():
    from ..routes import editor_readonly
    packs = wordpack_manager.get_all()
    return Div(
        Button("Select wordpack", data_uk_toggle='target: #pack-select'),
        Modal(ModalTitle("Wordpack selection"),
            Grid(Div(PacksSelect(packs, editor_readonly, hx_target='#editor', hx_swap='outerHTML'), cls='overflow-auto col-span-2 border-r-2'),
            Div(editor_readonly(packs[0].id) if packs else None, cls='col-span-3 h-full'),
            ModalCloseButton(),
            cols=5),
            id='pack-select')
    )
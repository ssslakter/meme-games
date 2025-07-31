from meme_games.core import *
from ..domain import game as gm
from meme_games.apps.word_packs.components import *

def PackSelect(game_state: gm.GameState):
    from ..routes import editor_readonly
    packs = wordpack_manager.get_all()
    return Div(
        Button("Select wordpack", data_uk_toggle='target: #pack-select'),
        Modal(ModalTitle("Wordpack selection"),
            Grid(Div(PacksSelect(packs, editor_readonly, hx_target='#editor', hx_swap='outerHTML'), cls='overflow-auto col-span-2 border-r-2'),
            Div(editor_readonly(game_state.config.wordpack.id), cls='col-span-3 h-full'),
            ModalCloseButton(),
            cols=5),
            id='pack-select')
    )


def GameContents(game_state: gm.GameState):
    from ..routes import start_game
    match game_state.state:
        case gm.StateMachine.ROUND_PLAYING:
            return CircleTimer(game_state.timer.rem_t, total=game_state.config.time_limit) 
        case gm.StateMachine.WAITING_FOR_PLAYERS:
            return Button("Start", cls=ButtonT.primary, hx_post=start_game,
                          disabled=not game_state.can_start())
        case gm.StateMachine.REVIEWING:
            return P("Waiting for the next round to start")
        case _: return None

def GameInfo(game_state: gm.GameState):
    wordpack = game_state.config.wordpack

    return Card(
        P(
            "Selected pack: ", Span(wordpack.name if wordpack else "No pack selected"),
        ),
        P("Game state: ", B(game_state.state.name)),
        GameContents(game_state),
        header=H4("Game info"),
    )
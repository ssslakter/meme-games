from meme_games.core import *
from meme_games.domain import is_host
from ..domain import game as gm
from meme_games.apps.word_packs.components import *

def PackSelect(game_state: gm.GameState):
    from ..routes import editor_readonly
    packs = wordpack_manager.get_all()
    return Div(
        Button("Select wordpack", data_uk_toggle='target: #pack-select'),
        Modal(ModalTitle("Wordpack selection"),
            Grid(Div(PacksSelect(packs, editor_readonly, hx_target='#editor', hx_swap='outerHTML'), cls='overflow-auto col-span-2 border-r-2'),
            Div(hx_post=editor_readonly.to(id=game_state.config.wordpack.id), hx_trigger='load', cls='col-span-3 h-full'),
            ModalCloseButton(),
            cols=5),
            id='pack-select')
    )

def ConfigLobby(r: gm.AliasPlayer, game_state: gm.GameState):
    from ..routes import update_settings
    if not is_host(r): return None
    return Div(
        Form(
             LabelRange('Time limit', value=str(game_state.config.time_limit), min=1, max=120, step=1, name='time_limit'),
             Details(
                 Summary("More settings"),
                 LabelInput('Max score', value=str(game_state.config.max_score), name='max_score'),
                 LabelInput('Max teams', value=str(game_state.config.max_teams), name='max_teams'),
                 ),
             Button("Update settings", cls=ButtonT.primary, type='submit'),
             hx_post = update_settings, hx_swap = 'none'
        )
    )


def GameContents(r: gm.AliasPlayer, game_state: gm.GameState):
    from ..routes import start_game
    match game_state.state:
        case gm.StateMachine.WAITING_FOR_PLAYERS:
            return Button(H1("Start"), cls=(ButtonT.primary, 'p-10'), hx_post=start_game,
                          disabled=not game_state.can_start()) if is_host(r) else None
        case gm.StateMachine.REVIEWING:
            return P("Waiting for the next round to start")
        case _: return None


def VoteButton(r: gm.AliasPlayer, game: gm.GameState):
    from ..routes import vote, start_round
    if game.state not in [gm.StateMachine.REVIEWING, gm.StateMachine.VOTING_TO_START] or r not in game.active_team: return None
    btn = Button(cls=(ButtonT.primary, 'p-10'), hx_swap='none')
    if r == game.active_player and game.active_team.all_voted():
        return Div(
            P("Start explaning when you're ready"),
            btn(H1("Start"), hx_post=start_round))
    return btn(H1("Not Ready" if r.voted else "Ready"), hx_post=vote.to(voted=not r.voted))



def GameControls(r: gm.AliasPlayer, game_state: gm.GameState):
    from meme_games.apps.word_packs.routes import index
    wordpack = game_state.config.wordpack
    if game_state.state in [gm.StateMachine.ROUND_PLAYING, gm.StateMachine.REVIEWING]: 
        return None

    return Div(
        H3("Game info"),
        DivHStacked(
        Div(P(
            "Selected pack: ",
            Button(wordpack.name, cls=ButtonT.text) if wordpack else "No pack selected", data_uk_toggle='target: #pack-select'),
        P("Game state: ", B(game_state.state)),
        GameContents(r, game_state),
        cls='space-y-6'
        ),
        VoteButton(r, game_state),
        ),
        cls='fixed bottom-0 left-0 w-full p-7 border',
        id='game-controls'
    )
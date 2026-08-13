from meme_games.core import *
from meme_games.domain import is_host, LobbyMember
from ..domain import game as gm
from meme_games.apps.word_packs.components import *
import fasthtml.common as fh

def RangeSlider(label: str, value: str, min: int, max: int, step: int, name: str):
    """A native range input, styleable via theme CSS (unlike Franken UI's closed-shadow-DOM Range)."""
    return Div(
        Div(FormLabel(label, fr=name, cls='m-0'),
            Span(value, id=f'{name}-value', cls='text-sm font-medium'),
            cls='flex items-center justify-between'),
        fh.Input(type='range', id=name, name=name, value=value, min=min, max=max, step=step,
                 cls='uk-range', _=f"on input set #{name}-value.textContent to my.value"),
        cls='space-y-2')


def PackSelect(game_state: gm.GameState):
    from ..routes import editor_readonly
    packs = wordpack_manager.get_all()
    return Div(
        Button(UkIcon('book-open', cls='mr-2'), "Select wordpack",
               cls=(ButtonT.default, 'w-full justify-start'), data_uk_toggle='target: #pack-select'),
        Modal(ModalTitle("Wordpack selection"),
            Grid(Div(PacksSelect(packs, editor_readonly, hx_target='#editor', hx_swap='outerHTML'), cls='overflow-auto col-span-2 border-r-2'),
            Div(hx_post=editor_readonly.to(id=game_state.config.wordpack.id), hx_trigger='load', cls='col-span-3 h-full'),
            ModalCloseButton(),
            cols=5),
            id='pack-select')
    )

def ConfigLobby(r: LobbyMember, game_state: gm.GameState):
    from ..routes import update_settings
    if not is_host(r): return None
    return Div(
        Form(
             RangeSlider('Time limit', value=str(game_state.config.time_limit), min=1, max=120, step=1, name='time_limit'),
             Details(
                 Summary("Advanced", cls='cursor-pointer px-3 py-2 font-medium'),
                 LabelInput('Max score', value=str(game_state.config.max_score), name='max_score'),
                 LabelInput('Max teams', value=str(game_state.config.max_teams), name='max_teams'),
                 cls='mg-more-settings space-y-3 rounded border'
                 ),
             Button("Update settings", cls=(ButtonT.primary, 'w-full'), type='submit'),
             hx_post = update_settings, hx_swap = 'none', cls='space-y-5'
        )
    )


def HostGameActions(r: LobbyMember, game: gm.GameState):
    from ..routes import pause_game, random_wordpack, restart_game, shuffle_teams
    if not is_host(r): return None
    playing = game.state == gm.StateMachine.ROUND_PLAYING
    waiting = game.state == gm.StateMachine.WAITING_FOR_PLAYERS
    return Div(
        H5('Host controls'),
        Div(
            Button(UkIcon('play' if game.timer.paused else 'pause', cls='mr-2 shrink-0'),
                   'Resume' if game.timer.paused else 'Pause', hx_post=pause_game, hx_swap='none',
                   disabled=not playing, cls=(ButtonT.default, 'w-full justify-start px-3 py-2')),
            Button(UkIcon('rotate-ccw', cls='mr-2 shrink-0'), 'Restart', hx_post=restart_game, hx_swap='none',
                   hx_confirm='Restart this game and reset all scores?', cls=(ButtonT.destructive, 'w-full justify-start px-3 py-2')),
            Button(UkIcon('shuffle', cls='mr-2 shrink-0'), 'Shuffle teams', hx_post=shuffle_teams, hx_swap='none',
                   disabled=not waiting or len(game.teams) < 2, cls=(ButtonT.default, 'w-full justify-start px-3 py-2')),
            Button(UkIcon('dices', cls='mr-2 shrink-0'), 'Random wordpack', hx_post=random_wordpack, hx_swap='none',
                   disabled=playing, cls=(ButtonT.default, 'w-full justify-start px-3 py-2')),
            cls='grid grid-cols-2 gap-3'),
        id='alias-host-controls', hx_swap_oob='true',
        cls='space-y-4', data_ui='host-game-controls')


def GameContents(r: LobbyMember, game_state: gm.GameState):
    from ..routes import start_game
    match game_state.state:
        case gm.StateMachine.WAITING_FOR_PLAYERS:
            return Button(UkIcon('play', cls='mr-2'), "Start game", cls=(ButtonT.primary, 'px-8 py-3'), hx_post=start_game,
                          disabled=not game_state.can_start()) if is_host(r) else None
        case gm.StateMachine.REVIEWING:
            return P("Waiting for the next round to start")
        case _: return None


def VoteButton(r: LobbyMember, game: gm.GameState):
    from ..routes import vote, start_round
    if game.state not in [gm.StateMachine.REVIEWING, gm.StateMachine.VOTING_TO_START] or r not in game.active_team: return None
    btn = Button(cls=(ButtonT.primary, 'px-8 py-3'), hx_swap='none')
    if r == game.active_player and game.all_voted(game.active_team):
        return Div(
            P("Your team is ready. Start when you are.", cls=TextT.muted),
            btn(UkIcon('play', cls='mr-2'), "Start round", hx_post=start_round),
            cls='flex flex-col items-center gap-3')
    voted = game.has_voted(r)
    return btn(UkIcon('rotate-ccw' if voted else 'check', cls='mr-2'),
               "Not ready" if voted else "I'm ready", hx_post=vote.to(voted=not voted),
               data_ui='ready-button', data_ready=str(voted).lower())



def GameControls(r: LobbyMember, game_state: gm.GameState):
    from meme_games.apps.word_packs.routes import index
    wordpack = game_state.config.wordpack
    if game_state.state in [gm.StateMachine.ROUND_PLAYING, gm.StateMachine.REVIEWING]: 
        return None

    return Card(
        Div(
            Div(
                P("Game state", cls=TextT.muted),
                H3(str(game_state.state), cls='mg-game-status'),
                data_ui='game-status'),
            Div(
                P("Word pack", cls=TextT.muted),
                Button(wordpack.name, cls=ButtonT.text) if wordpack else "No pack selected",
                data_uk_toggle='target: #pack-select'),
            cls='grid gap-6 text-center sm:grid-cols-2'),
        Div(GameContents(r, game_state), VoteButton(r, game_state),
            cls='flex flex-wrap items-center justify-center gap-4'),
        cls='mg-game-controls w-full', body_cls='space-y-5 p-6',
        data_ui='game-controls',
        id='game-controls'
    )

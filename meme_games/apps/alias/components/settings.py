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


def PackSelectContents(r: LobbyMember, game_state: gm.GameState) -> FT:
    from ..routes import editor_readonly, select_pack
    packs = wordpack_manager.get_all()
    wordpack = game_state.config.wordpack
    return Div(Div(PacksSelect(packs, editor_readonly, hx_target='#editor', hx_swap='outerHTML'),
                   cls='mg-pack-select-list overflow-auto'),
                WordPackEditor(wordpack, readonly=True,
                               form_kwargs=dict(hx_post=select_pack, hx_swap='none'),
                               submit_button=Button('Select wordpack' if is_host(r) else 'Must be host to select',
                                                    disabled=not is_host(r)),
                               cls='mg-pack-select-editor',
                               hx_on__after_request="UIkit.modal('#pack-select').hide()"),
                ModalCloseButton(), cls='mg-pack-select-layout')


def PackSelectButton() -> FT:
    return Button(UkIcon('book-open', cls='mr-2'), 'Select wordpack',
                  cls=(ButtonT.default, 'w-full justify-start'), data_uk_toggle='target: #pack-select')


def PackSelectModal(game_state: gm.GameState) -> FT:
    from ..routes import pack_select
    return Modal(ModalTitle('Wordpack selection'),
                 Div(P('Loading wordpacks…', cls=TextT.muted), id='pack-select-content'),
                 id='pack-select', hx_get=pack_select, hx_trigger='shown',
                 hx_target='#pack-select-content', hx_swap='innerHTML', cls='mg-pack-select-modal')


def PackSelect(game_state: gm.GameState) -> FT:
    return Div(PackSelectButton(), PackSelectModal(game_state))

def ConfigLobby(r: LobbyMember, game_state: gm.GameState) -> Optional[FT]:
    from ..routes import update_settings
    if not is_host(r): return None
    return Div(
        Form(
             RangeSlider('Time limit', value=str(game_state.config.time_limit), min=1, max=120, step=1, name='time_limit'),
             Details(
                 Summary("Advanced", cls='cursor-pointer px-3 py-2 font-medium'),
                 Div(
                     Div(
                         CheckboxX(id='player-words', name='player_words', checked=game_state.config.player_words),
                         FormLabel('Players write the words', fr='player-words', cls='m-0 cursor-pointer'),
                         cls='flex items-center gap-2'),
                     Div(
                         CheckboxX(id='hide-skipped-words', name='hide_skipped_words',
                                   checked=game_state.config.hide_skipped_words),
                         FormLabel('Hide skipped words from other players', fr='hide-skipped-words', cls='m-0 cursor-pointer'),
                         cls='flex items-center gap-2'),
                     RangeSlider('Word collection time', value=str(game_state.config.word_collection_time), min=10, max=180, step=5, name='word_collection_time'),
                     LabelInput('Max score', value=str(game_state.config.max_score), name='max_score'),
                     LabelInput('Max teams', value=str(game_state.config.max_teams), name='max_teams'),
                     cls='mg-more-settings-body space-y-3 p-3 pt-2'),
                 cls='mg-more-settings rounded border'
                 ),
             Button("Update settings", cls=(ButtonT.primary, 'w-full'), type='submit'),
             hx_post = update_settings, hx_swap = 'none', cls='space-y-5'
        )
    )


def HostGameActions(r: LobbyMember, game: gm.GameState):
    from ..routes import pause_game, random_wordpack, shuffle_teams
    if not is_host(r): return None
    playing = game.state == gm.StateMachine.ROUND_PLAYING
    waiting = game.state == gm.StateMachine.WAITING_FOR_PLAYERS
    return Div(
        H5('Host controls'),
        Div(
            Button(UkIcon('play' if game.timer.paused else 'pause', cls='mr-2 shrink-0'),
                   'Resume' if game.timer.paused else 'Pause', hx_post=pause_game, hx_swap='none',
                   disabled=not playing, cls=(ButtonT.default, 'w-full justify-start px-3 py-2')),
            Button(UkIcon('rotate-ccw', cls='mr-2 shrink-0'), 'Restart', type='button',
                   data_uk_toggle='target: #alias-restart-confirm',
                   cls=(ButtonT.destructive, 'w-full justify-start px-3 py-2')),
            Button(UkIcon('shuffle', cls='mr-2 shrink-0'), 'Shuffle teams', hx_post=shuffle_teams, hx_swap='none',
                   disabled=not waiting or len(game.teams) < 2, cls=(ButtonT.default, 'w-full justify-start px-3 py-2')),
            Button(UkIcon('dices', cls='mr-2 shrink-0'), 'Random wordpack', hx_post=random_wordpack, hx_swap='none',
                   disabled=playing, cls=(ButtonT.default, 'w-full justify-start px-3 py-2')),
            cls='grid grid-cols-2 gap-3'),
        id='alias-host-controls', hx_swap_oob='true',
        cls='space-y-4', data_ui='host-game-controls')


def RestartConfirmation() -> FT:
    from ..routes import restart_game
    return Modal(
        ModalCloseButton(),
        P('This resets the game and every score. Teams stay together.'),
        header=ModalTitle('Restart Alias?'),
        footer=Div(
            Button('Cancel', type='button', cls=(ButtonT.default, 'uk-modal-close')),
            Button('Restart', hx_post=restart_game, hx_swap='none', cls=ButtonT.destructive,
                   _="on htmx:afterRequest call UIkit.modal('#alias-restart-confirm').hide()"),
            cls='flex justify-end gap-3'),
        id='alias-restart-confirm', dialog_cls='max-w-md')


def GameContents(r: LobbyMember, game_state: gm.GameState):
    from ..routes import start_game
    match game_state.state:
        case gm.StateMachine.WAITING_FOR_PLAYERS:
            return Button(UkIcon('play', cls='mr-2'), "Start game", cls=(ButtonT.primary, 'px-8 py-3'), hx_post=start_game,
                          disabled=not game_state.can_start()) if is_host(r) else None
        case gm.StateMachine.REVIEWING:
            return P("Waiting for the next round to start")
        case gm.StateMachine.BETWEEN_WORD_ROUNDS:
            return P('Round 2: explanations may contain only one word.', cls=TextT.muted)
        case gm.StateMachine.FINISHED:
            return P("The shared word pack is complete.")
        case _: return None


def VoteButton(r: LobbyMember, game: gm.GameState):
    from ..routes import vote, start_round
    between_rounds = game.state == gm.StateMachine.BETWEEN_WORD_ROUNDS
    if between_rounds and not game.team_by_player(r): return None
    if not between_rounds and (game.state not in [gm.StateMachine.REVIEWING, gm.StateMachine.VOTING_TO_START]
                               or r not in game.active_team): return None
    btn = Button(cls=(ButtonT.primary, 'px-8 py-3'), hx_swap='none')
    if (game.state == gm.StateMachine.VOTING_TO_START and r == game.active_player and
            game.all_voted(game.active_team)):
        return Div(
            P("Your team is ready. Start when you are.", cls=TextT.muted),
            btn(UkIcon('play', cls='mr-2'), "Start round", hx_post=start_round),
            cls='flex flex-col items-center gap-3')
    voted = game.has_voted(r)
    return btn(UkIcon('rotate-ccw' if voted else 'check', cls='mr-2'),
               "Not ready" if voted else "I'm ready", hx_post=vote.to(voted=not voted),
               data_ui='ready-button', data_ready=str(voted).lower())



def GameControls(r: LobbyMember, game_state: gm.GameState):
    wordpack = game_state.config.wordpack
    if game_state.state in [gm.StateMachine.COLLECTING_WORDS, gm.StateMachine.ROUND_PLAYING, gm.StateMachine.REVIEWING]:
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
        Div(
            P(f'{game_state.active_player.name} is explaining'),
            P(f'{game_state.active_guesser.name} is guessing' if game_state.active_guesser else
              f'Team {list(game_state.teams).index(game_state.active_team.id) + 1} is guessing', cls=TextT.muted),
            cls='text-center') if game_state.state in [gm.StateMachine.VOTING_TO_START,
                                                       gm.StateMachine.BETWEEN_WORD_ROUNDS] else None,
        Div(GameContents(r, game_state), VoteButton(r, game_state),
            cls='flex flex-wrap items-center justify-center gap-4'),
        cls='mg-game-controls w-full', body_cls='space-y-5 p-6',
        data_ui='game-controls',
        id='game-controls'
    )

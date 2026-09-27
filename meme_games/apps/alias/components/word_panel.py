from meme_games.core import *
from meme_games.domain import LobbyMember
from meme_games.apps.shared import CircleTimer, ColoredPoints
from ..domain import game as gm
from .settings import VoteButton


def CurrentWord(game: gm.GameState):
    subtitle = (f'Explain to: {game.active_guesser.user.name}'
                if len(game.teams) == 1 and game.active_guesser else
                'Round 2: one word only.' if game.config.player_words and game.word_round == 2 else
                'Current word')
    return Div(P(subtitle, cls=TextT.muted, data_ui='explaining-to'), H1(game.active_word, cls='mg-current-word'),
               id='current_word', hx_swap_oob='true', data_ui='current-word',
               cls='mg-current-word-card border bg-card px-8 py-10 text-center shadow-sm')


def WordCollectionStatus(r: LobbyMember, game: gm.GameState) -> FT:
    submitted = len(game.submitted_words.get(r.uid, []))
    status = 'submitted' if r.uid in game.submitted_players else 'entered'
    return P(f'{submitted} words {status}', id='word-collection-status', cls=TextT.muted)


def WordCollectionPanel(r: LobbyMember, game: gm.GameState) -> FT:
    from ..routes import submit_words
    saved_words = '\n'.join(game.submitted_words.get(r.uid, []))
    finalized = r.uid in game.submitted_players
    return Card(
        Div(CircleTimer(game.timer.rem_t, total=game.config.word_collection_time),
            H2('Write words for the shared pack'),
            P('Add one word per line. Words are submitted when time runs out.', cls=TextT.muted),
            id='word-collection-timer', cls='flex flex-col items-center gap-3 text-center'),
        Form(
            TextArea(saved_words, name='words', rows=7, placeholder='apple\nspaceship\n...', cls='w-full resize-y',
                     readonly=finalized,
                     oninput="document.getElementById('word-collection-status').textContent = this.value.split(/\\r?\\n/).filter(line => line.trim()).length + ' words entered'"),
            WordCollectionStatus(r, game),
            Button('Words submitted' if finalized else 'Submit words', type='button', disabled=finalized,
                   cls=(ButtonT.primary, 'w-full'), hx_post=submit_words.to(finalized='True'),
                   hx_include='closest form', hx_target='closest .mg-round-center', hx_swap='outerHTML'),
            hx_post=submit_words.to(finalized='True') if not finalized else None,
            hx_trigger='timer:expired from:#word-collection-timer' if not finalized else None,
            hx_target='closest .mg-round-center', hx_swap='outerHTML', cls='space-y-3'),
        cls='mg-round-center w-full min-w-0 p-6 md:p-10', body_cls='space-y-6',
        data_ui='word-collection')


def ExplainerPanel(r: LobbyMember, game: gm.GameState):
    from ..routes import guess
    if r != game.active_player: return None
    def action(icon: str, label: str, style, correct: bool):
        return Button(UkIcon(icon, width=22, height=22), Span(label, cls='text-xl font-semibold'),
                      cls=(style, 'inline-flex items-center gap-2 px-7 py-3'),
                      hx_post=guess.to(correct=str(correct)), hx_swap='none')
    return Div(
        CurrentWord(game),
        Div(action('circle-check', 'Guessed', ButtonT.primary, True),
            None if game.config.disable_skip else action('circle-x', 'Skip', ButtonT.default, False),
            cls='flex justify-center gap-4'),
        cls='space-y-5')


def WordEntryScore(guess: gm.GuessEntry):
    return Div(" Score: ", ColoredPoints(guess.points), cls='p-1', id=f'sc-{guess.id}', hx_swap_oob='true')


RESULT_CLS = {
    'guessed': 'bg-green-50/80 border-green-200 dark:bg-green-950/40 dark:border-green-800',
    'skipped': 'bg-red-50/80 border-red-200 dark:bg-red-950/40 dark:border-red-900',
}


def WordEntry(guess: gm.GuessEntry, game: gm.GameState):
    from ..routes import change_guess_points
    result = 'skipped' if guess.was_skipped() else 'guessed'
    word = Span(guess.word, cls='text-lg break-words text-center', data_ui='word-text')
    if game.state == gm.StateMachine.REVIEWING:
        def adjust(delta: int, label: str):
            return Button(label, hx_post=change_guess_points.to(guess_id=guess.id, delta=delta),
                          hx_swap='none', cls=(ButtonT.default, 'flex-shrink-0'))
        body = Div(adjust(-1, '-'),
                   Div(WordEntryScore(guess), word, cls='flex flex-col items-center justify-between min-w-0'),
                   adjust(1, '+'), cls='flex w-full items-center justify-between gap-3')
    else:
        body = Div(word, UkIcon('circle-check' if result == 'guessed' else 'circle-x', width=18, height=18),
                   cls='flex items-center justify-between gap-3')
    return Div(body, cls=f'mg-game-card mg-word-entry w-full px-3 py-2 uk-card {RESULT_CLS[result]}',
               data_ui='word-entry', data_result=result)


def visible_round_guesses(r: LobbyMember | None, game: gm.GameState) -> list[gm.GuessEntry]:
    '''Skipped words stay with the explainer when that setting is on. Everyone else sees guesses.'''
    owner = game.review_player if game.state == gm.StateMachine.REVIEWING else game.active_player
    if not game.hides_skipped_words() or r == owner: return list(game.guess_log)
    return [guess for guess in game.guess_log if not guess.was_skipped()]


def RoundLog(r: LobbyMember | None, game: gm.GameState) -> FT:
    visible_guesses = visible_round_guesses(r, game)
    entries = ((WordEntry(guess, game) for guess in reversed(visible_guesses)) if visible_guesses else
               (P('Words will appear here as the round progresses.', cls=TextT.muted),))
    return DivVStacked(entries, cls='w-full gap-2 max-h-[45vh] overflow-y-auto pr-1', id='guess_log',
                       hx_swap_oob='true', data_ui='round-log')


def GuessCount(r: LobbyMember | None, game: gm.GameState):
    return Span(len(visible_round_guesses(r, game)), id='guess_count', hx_swap_oob='true',
                cls='rounded-full bg-secondary px-2 py-0.5 text-sm')


def GuessPanel(r: LobbyMember | None, game: gm.GameState) -> Optional[FT]:
    if game.state not in [gm.StateMachine.ROUND_PLAYING, gm.StateMachine.REVIEWING]: return None
    return Card(
        Div(H3('Finished words'), GuessCount(r, game), cls='flex items-center justify-between'),
        RoundLog(r, game),
        cls='mg-round-history w-full min-w-0', body_cls='space-y-4 p-4',
        data_ui='round-history')


ROUND_STATUS = {
    'paused': 'Paused',
    'last-word': 'Time is up — last word',
    'playing': 'Round in progress',
    'review': 'Review the round',
}


def round_phase(game: gm.GameState) -> str:
    if game.state != gm.StateMachine.ROUND_PLAYING: return 'review'
    if game.timer.paused: return 'paused'
    return 'last-word' if game.timer.finished else 'playing'


def RoundContent(r: LobbyMember, game: gm.GameState):
    if game.state != gm.StateMachine.ROUND_PLAYING:
        return VoteButton(r, game) or P('Waiting for the next team to confirm the score.', cls=TextT.muted)
    if r == game.active_player: return ExplainerPanel(r, game)
    return Div(H2(f'{game.active_player.user.name} is explaining'),
               P(f"{game.active_guesser.user.name} is guessing" if game.active_guesser else
                 'Guessed words show up below.', cls=TextT.muted),
               cls='space-y-2 text-center')


def RoundCenter(r: LobbyMember, game: gm.GameState):
    phase = round_phase(game)
    playing = phase != 'review'
    return Card(
        Div(
            CircleTimer(game.timer.rem_t, total=game.config.time_limit, paused=game.timer.paused) if playing
            else UkIcon('clipboard-check', width=48, height=48),
            P(ROUND_STATUS[phase],
              cls='font-semibold text-amber-600 dark:text-amber-400' if phase in ('paused', 'last-word') else TextT.muted,
              data_ui='round-status', data_phase=phase),
            cls='flex flex-col items-center gap-2'),
        RoundContent(r, game),
        cls=f'mg-round-center flex w-full min-w-0 flex-col justify-center gap-8 p-6 md:p-10 {"min-h-[20rem]" if playing else ""}',
        data_ui='round-center')


def WordPanel(r: LobbyMember, game: gm.GameState):
    '''Every receiver gets the same layout in both phases: round card on top, finished words below.'''
    if game.state == gm.StateMachine.COLLECTING_WORDS:
        return Div(WordCollectionPanel(r, game), cls='mg-game-panel mg-word-panel w-full',
                   data_ui='word-panel', data_stage='word-collection')
    if game.state not in [gm.StateMachine.ROUND_PLAYING, gm.StateMachine.REVIEWING]: return None
    return Div(
        RoundCenter(r, game),
        GuessPanel(r, game),
        cls='mg-game-panel mg-word-panel flex w-full flex-col gap-4',
        data_ui='word-panel', data_stage='round' if game.state == gm.StateMachine.ROUND_PLAYING else 'review')

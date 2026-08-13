from meme_games.core import *
from meme_games.domain import LobbyMember
from meme_games.apps.shared import CircleTimer, ColoredPoints
from ..domain import game as gm
from .settings import VoteButton


def CurrentWord(game: gm.GameState):
    return Div(P('Current word', cls=TextT.muted), H1(game.active_word, cls='mg-current-word'),
               id='current_word', hx_swap_oob='true', data_ui='current-word',
               cls='mg-current-word-card border bg-card px-8 py-10 text-center shadow-sm')


def ExplainerPanel(r: LobbyMember, game: gm.GameState):
    from ..routes import guess
    if not r == game.active_player: return None
    return Div(
        CurrentWord(game),
        Div(
            Button(UkIcon('circle-check', width=22, height=22), Span('Guessed', cls='text-xl font-semibold'),
                   cls=(ButtonT.primary, 'inline-flex items-center gap-2 px-7 py-3'),
                   hx_post=guess.to(correct='True'), hx_swap='none'),
            Button(UkIcon('circle-x', width=22, height=22), Span('Skip', cls='text-xl font-semibold'),
                   cls=(ButtonT.default, 'inline-flex items-center gap-2 px-7 py-3'),
                   hx_post=guess.to(correct='False'), hx_swap='none'),
            cls='flex justify-center gap-4'
        ),
        cls='space-y-5'
    )


def WordEntryScore(guess: gm.GuessEntry):
        return Div(" Score: ", ColoredPoints(guess.points), cls='p-1', id=f'sc-{guess.id}', hx_swap_oob='true')


def WordEntry(guess: gm.GuessEntry, game: gm.GameState):
    from ..routes import change_guess_points
    body = Span(guess.word, cls='text-lg break-words text-center')
    if game.state == gm.StateMachine.REVIEWING:
        btn = lambda delta: Button(hx_post=change_guess_points.to(guess_id=guess.id, delta=delta), hx_swap='none', cls=(ButtonT.default, ' flex-shrink-0'))
        score = WordEntryScore(guess)
        mid = Div(score, body, cls='flex flex-col items-center justify-between min-w-0')
        body = Div(btn(-1)('-'), mid, btn(1)('+'), cls='flex w-full items-center justify-between gap-3')
    result = 'guessed' if guess.points > 0 else 'skipped'
    if game.state != gm.StateMachine.REVIEWING:
        body = Div(body, UkIcon('circle-check' if result == 'guessed' else 'circle-x', width=18, height=18),
                   cls='flex items-center justify-between gap-3')
    result_cls = ('bg-green-50/80 border-green-200 dark:bg-green-950/40 dark:border-green-800'
                  if result == 'guessed' else
                  'bg-red-50/80 border-red-200 dark:bg-red-950/40 dark:border-red-900')
    return Div(body, cls=f'mg-game-card mg-word-entry w-full px-3 py-2 uk-card {result_cls}',
               data_ui='word-entry', data_result=result)


def RoundLog(guesses: list[gm.GuessEntry], game: gm.GameState):
    entries = ((WordEntry(guess, game) for guess in reversed(guesses)) if guesses else
               (P('Words will appear here as the round progresses.', cls=TextT.muted),))
    log_size = 'min-h-0 flex-1 overflow-y-auto pr-1' if game.state == gm.StateMachine.ROUND_PLAYING else 'max-h-[45vh] overflow-y-auto pr-1'
    return DivVStacked(entries, cls=f'w-full gap-2 {log_size}', id='guess_log',
                       hx_swap_oob='true', data_ui='round-log')


def GuessCount(game: gm.GameState):
    return Span(len(game.guess_log), id='guess_count', hx_swap_oob='true',
                cls='rounded-full bg-secondary px-2 py-0.5 text-sm')



def GuessPanel(game: gm.GameState, footer=None):
    if game.state not in [gm.StateMachine.ROUND_PLAYING, gm.StateMachine.REVIEWING]: return None
    playing = game.state == gm.StateMachine.ROUND_PLAYING
    return Card(
        Div(H3('Finished words'), GuessCount(game),
            cls='flex items-center justify-between'),
        RoundLog(game.guess_log, game),
        footer,
        cls=('mg-round-history order-2 flex min-h-0 min-w-0 flex-1 flex-col md:order-1' if playing
             else 'mg-round-history order-2 min-w-0 md:order-1'),
        body_cls=('flex min-h-0 flex-1 flex-col gap-4 p-4' if playing else 'space-y-4 p-4'),
        data_ui='round-history')


def RoundCenter(r: LobbyMember, game: gm.GameState):
    playing = game.state == gm.StateMachine.ROUND_PLAYING
    last_word = playing and game.timer.finished
    content = (ExplainerPanel(r, game) if r == game.active_player else
               Div(H2(f'{game.active_player.user.name} is explaining'),
                   P('Follow along—the results appear in the history on the left.', cls=TextT.muted),
                   cls='space-y-2 text-center')) if playing else VoteButton(r, game)
    return Card(
        Div(
            CircleTimer(game.timer.rem_t, total=game.config.time_limit, paused=game.timer.paused) if playing
            else UkIcon('clipboard-check', width=48, height=48),
            P('Paused' if game.timer.paused else 'Time is up — last word' if last_word else 'Round in progress' if playing else 'Review the round',
              cls='font-semibold text-amber-600 dark:text-amber-400' if last_word or game.timer.paused else TextT.muted,
              data_ui='round-status', data_phase='paused' if game.timer.paused else 'last-word' if last_word else 'playing' if playing else 'review'),
            cls='flex flex-col items-center gap-2'),
        content,
        cls='mg-round-center order-1 flex min-h-[28rem] w-full min-w-0 flex-col justify-center gap-8 p-6 md:order-2 md:p-10',
        data_ui='round-center')


def WordPanel(r: LobbyMember, game: gm.GameState):
    if game.state not in [gm.StateMachine.ROUND_PLAYING, gm.StateMachine.REVIEWING]: return None
    if game.state == gm.StateMachine.REVIEWING:
        return Div(
            GuessPanel(game, VoteButton(r, game)),
            cls='mg-game-panel mg-word-panel w-full',
            data_ui='word-panel', data_stage='review')
    return Div(
        RoundCenter(r, game),
        cls='mg-game-panel mg-word-panel w-full',
        data_ui='word-panel', data_stage='round')

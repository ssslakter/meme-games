from meme_games.core import *
from meme_games.apps.shared import CircleTimer
from ..domain import game as gm



def CurrentWord(game: gm.GameState):
    return Div("Current word: ", Span(game.active_word),
               id='current_word', hx_swap_oob='true')


def ExplainerPanel(r: gm.AliasPlayer, game: gm.GameState):
    from ..routes import guess
    if not r == game.active_player: return None
    return Div(
        Div(CurrentWord(game), cls='text-center mb-4'),
        Div(
            Button(H2("Guessed"), cls=(ButtonT.primary, " px-8 py-3 text-lg"), hx_post=guess.to(correct=True), hx_swap='none'),
            Button(H2("Skip"), cls="px-8 py-3 text-lg", hx_post=guess.to(correct=False), hx_swap='none'),
            cls='flex justify-center space-x-4'
        ),
        cls='pb-6'
    )

def WordEntry(guess: gm.GuessEntry, game: gm.GameState):
    from ..routes import change_guess_points
    body = [Div(Span(guess.word, cls='text-lg'))]
    if game.state == gm.StateMachine.REVIEWING:
        btn = lambda delta: Button(hx_post=change_guess_points.to(guess_id=guess.id, points=guess.points+delta), hx_swap='none')
        cls = 'bg-red-100' if guess.points < 0 else 'bg-green-100' if guess.points > 0 else 'bg-gray-200'
        body = [btn(-1)('-'), *body,Div(" Score: ", Span(guess.points, cls=cls)), btn(1)('+')]
    return Div(
        DivHStacked(*body, data_guess_id=guess.id, 
        hx_swap_oob=f"outerHTML:[data-guess-id='{guess.id}']",
        cls='justify-center'),
        cls='w-full px-2 uk-card w-64')


def RoundLog(guesses: list[gm.GuessEntry], game: gm.GameState):
    return DivVStacked((WordEntry(guess, game) for guess in guesses), cls='space-y-1')



def GuessPanel(game: gm.GameState):
    if game.state not in [gm.StateMachine.ROUND_PLAYING, gm.StateMachine.REVIEWING]: return None
    return DivVStacked(
        CircleTimer(game.timer.rem_t, total=game.config.time_limit),
        RoundLog(game.guess_log, game),
        cls='flex-col-reverse',
        id='guess_panel',
        hx_swap_oob='true')

def WordPanel(r: gm.AliasPlayer, game: gm.GameState):
    return Div(
        GuessPanel(game),
        (ExplainerPanel(r, game) if game.state==gm.StateMachine.ROUND_PLAYING else None),
        cls='fixed bottom-0 left-1/2 transform -translate-x-1/2'
        )

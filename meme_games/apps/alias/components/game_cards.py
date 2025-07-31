from meme_games.core import *
from meme_games.apps.user import *
from ..domain import game as gm


def TeamCard(r: User | gm.AliasPlayer, team: gm.Team):
    from ..routes import join_team
    return Card(
        *(DivFullySpaced(UserInfo(r, m.user, m.is_connected), Span(team.points), cls='bg-green-100 rounded-md' if m.voted else '') for m in team.members),
        Form(Input(type='hidden', name='team_id', value=team.id),
            Button("Join"), hx_post=join_team, hx_swap='none') if not r in team else None
    )

def NewTeamCard():
    from ..routes import new_team
    return Card(Button("New team", hx_post=new_team))


def VoteButton(r: gm.AliasPlayer, game: gm.GameState):
    from ..routes import vote
    if game.state not in [gm.StateMachine.REVIEWING, gm.StateMachine.VOTING_TO_START] or r not in game.active_team: return None
    return Card(Button("Unvote" if r.voted else "Vote", cls=ButtonT.primary, 
                  hx_post=vote.to(voted=not r.voted)), 
                  cls=f"fixed bottom-0 -translate-x-1/2")


def GuessPanel(r: gm.AliasPlayer, game: gm.GameState):
    if game.state not in [gm.StateMachine.ROUND_PLAYING, gm.StateMachine.REVIEWING]: return None
    return Card(
        RoundLog(game.guess_log, game),
        ExplainerPanel(r, game) if game.state==gm.StateMachine.ROUND_PLAYING else None,
        id='word_panel',
        hx_swap_oob='true',
    )


def WordEntry(guess: gm.GuessEntry, game: gm.GameState):
    from ..routes import change_guess_points
    body = [Div(Span(guess.word, cls='text-lg'))]
    if game.state == gm.StateMachine.REVIEWING:
        btn = lambda delta: Button(hx_post=change_guess_points.to(guess_id=guess.id, points=guess.points+delta), hx_swap='none')
        cls = 'bg-red-100' if guess.points < 0 else 'bg-green-100' if guess.points > 0 else 'bg-gray-200'
        body = [btn(-1)('-'), *body,Div(" Score: ", Span(guess.points, cls=cls)), btn(1)('+')]
    return DivHStacked(
        *body,
        data_guess_id=guess.id,
        hx_swap_oob=f"outerHTML:[data-guess-id='{guess.id}']"
    )


def RoundLog(guesses: list[gm.GuessEntry], game: gm.GameState):
    return DivVStacked(WordEntry(guess, game) for guess in guesses)

def ExplainerPanel(r: gm.AliasPlayer, game: gm.GameState):
    from ..routes import guess
    if not r == game.active_player: return None
    return Div(
        Div("Current word: ", Span(game.active_word)),
        Button("Guessed", cls=ButtonT.primary,hx_post=guess.to(correct=True)),
        Button("Skip", hx_post=guess.to(correct=False)),
    )
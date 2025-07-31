from meme_games.core import *
from meme_games.apps.user import *
from ..domain import game as gm


def TeamCard(r: User | gm.AliasPlayer, team: gm.Team):
    from ..routes import join_team
    return Card(
        *(DivFullySpaced(UserInfo(r, m.user, m.is_connected), Span(m.score)) for m in team.members),
        Form(Input(type='hidden', name='team_id', value=team.id),
            Button("Join"), hx_post=join_team, hx_swap='none') if not r in team else None
    )
    
def NewTeamCard():
    from ..routes import new_team
    return Card(Button("New team", hx_post=new_team))

def VotePanel(r: User | gm.AliasPlayer, game: gm.GameState):
    if game.state not in [gm.StateMachine.REVIEWING, gm.StateMachine.VOTING_TO_START] or r not in game.active_team: return None
    team_members = Div(
            *[UserName(r, m, cls='bg-green-500' if m.voted else '') for m in game.active_team.members],
            cls="flex flex-col gap-1")
    return Card(
        team_members,
        VoteButton(r)
    )

def VoteButton(r: gm.AliasPlayer):
    from ..routes import vote
    return Button("Unvote" if r.voted else "Vote", cls=ButtonT.primary, 
                  hx_post=vote.to(voted=not r.voted))


def GuessPanel(r: gm.AliasPlayer, game: gm.GameState):
    if game.state != gm.StateMachine.ROUND_PLAYING: return None
    return Card(
        RoundLog(game.guess_log),
        ExplainerPanel(r, game),
        id='word_panel',
        hx_swap_oob='true',
    )


def WordEntry(guess: gm.GuessEntry, lobby: gm.GameState):
    body = [Div(Span(guess.word, cls='text-lg'),
            Span("Score: ", guess.points))]
    if lobby.state == gm.StateMachine.REVIEWING:
        body = [Button('-'), *body, Button('+')]
    return DivHStacked(
        body,
        data_id=guess.id,
    )


def RoundLog(guesses: list[gm.GuessEntry]):
    return DivVStacked(Div(guess.word) for guess in guesses)

def ExplainerPanel(r: gm.AliasPlayer, game: gm.GameState):
    from ..routes import guess
    if not r == game.active_player: return None
    return Div(
        Div("Current word: ", Span(game.active_word)),
        Button("Guessed", cls=ButtonT.primary,hx_post=guess.to(correct=True)),
        Button("Skip", hx_post=guess.to(correct=False)),
    )
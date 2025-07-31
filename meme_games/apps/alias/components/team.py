from meme_games.core import *
from meme_games.apps.user import *
from .word_panel import *
from ..domain import game as gm

card_cls = 'w-[20rem]'
def TeamCard(r: User | gm.AliasPlayer, team: gm.Team, game: gm.GameState):
    from ..routes import join_team
    winner_classes = 'relative ring-4 ring-amber-400 shadow-lg' if game.is_winner(team) else ''

    return Card(
        WinnerTag() if game.is_winner(team) else None,
        *(DivFullySpaced(UserInfo(r, m.user, m.is_connected), Div(Span(team.points),PotentialScore(team, game)), 
                         cls=('bg-green-100 rounded-md dark:bg-green-500' if m.voted else '', 'w-full truncate')) 
                         for m in team.members),
        Form(Input(type='hidden', name='team_id', value=team.id),
            Button("Join"), hx_post=join_team, hx_swap='none') if not r in team else None,
        id='id-'+team.id,
        hx_swap_oob='true',
        cls=f'{card_cls} {winner_classes}'
    )

def NewTeamCard():
    from ..routes import new_team
    return Card(Button("New team", hx_post=new_team, hx_swap='none'), cls=card_cls)


def WinnerTag():
    return Div(
        "🏆 WINNER!",
        cls="absolute -top-4 -right-4 bg-amber-400 text-sm font-bold px-4 py-2 rounded-full shadow-lg transform rotate-6"
    )

def PotentialScore(team: gm.Team, game: gm.GameState):
    if team != game.active_team or game.state!=gm.StateMachine.REVIEWING: return None
    score = sum(g.points for g in game.guess_log)
    return Span('(',ColoredPoints(score),')')
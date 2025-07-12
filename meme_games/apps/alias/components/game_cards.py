from meme_games.core import *
from meme_games.apps.user import *
from ..domain import *


def TeamCard(r: User | AliasPlayer, team: Team):
    from ..routes import join_team
    return Card(
        *(DivFullySpaced(UserInfo(r, m.user), Span(m.score)) for m in team.members),
        Form(Input(type='hidden', name='team_id', value=team.id),
            Button("Join"), hx_post=join_team, hx_swap='none') if not r in team else None
    )
    
def NewTeamCard():
    from ..routes import new_team
    return Card(Button("New team", hx_post=new_team))
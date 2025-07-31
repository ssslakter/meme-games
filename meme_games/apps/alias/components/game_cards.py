from meme_games.core import *
from meme_games.apps.user import *
from .word_panel import *
from ..domain import game as gm

card_cls = 'w-[20rem]'
def TeamCard(r: User | gm.AliasPlayer, team: gm.Team):
    from ..routes import join_team
    return Card(
        *(DivFullySpaced(UserInfo(r, m.user, m.is_connected), Span(team.points), 
                         cls=('bg-green-100 rounded-md' if m.voted else '', 'w-full truncate')) 
                         for m in team.members),
        Form(Input(type='hidden', name='team_id', value=team.id),
            Button("Join"), hx_post=join_team, hx_swap='none') if not r in team else None,
        id='id-'+team.id,
        hx_swap_oob='true',
        cls=card_cls
    )

def NewTeamCard():
    from ..routes import new_team
    return Card(Button("New team", hx_post=new_team, hx_swap='none'), cls=card_cls)

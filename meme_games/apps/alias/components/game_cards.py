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
    from ..routes import vote
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
    return Form(
            Input(type='hidden', name='voted', value=str(not r.voted).lower()),
            Button("Unvote" if r.voted else "Vote", cls=ButtonT.primary),
            hx_post=vote)
     
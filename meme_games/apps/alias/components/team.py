from meme_games.core import *
from meme_games.apps.user import *
from meme_games.domain import LobbyMember
from .word_panel import *
from ..domain import game as gm

card_cls = "min-w-0"


def TeamCard(r: User | LobbyMember, team: gm.Team, game: gm.GameState):
    from ..routes import join_team

    winner_classes = (
        "relative ring-4 ring-amber-400 shadow-lg" if game.is_winner(team) else ""
    )

    return Card(
        WinnerTag() if game.is_winner(team) else None,
        DivFullySpaced(
            H4(f'Team {list(game.teams).index(team.id) + 1}', cls='mg-team-name'),
            Div(Span(team.points, cls='mg-team-score tabular-nums'), PotentialScore(team, game),
                cls='flex items-center gap-2')),
        *(
            DivFullySpaced(
                UserInfo(r, m.user, m.is_connected, m.is_host, avatar_cls='h-12 w-12'),
                Span('Ready', cls='mg-ready-badge rounded-full bg-green-100 px-2 py-1 text-xs font-semibold text-green-800 dark:bg-green-900 dark:text-green-100') if game.has_voted(m) else None,
                cls="mg-team-member w-full truncate",
                data_ready=str(game.has_voted(m)).lower(),
            )
            for m in team.members
        ),
        (
            Form(
                Input(type="hidden", name="team_id", value=team.id),
                Button("Join"),
                hx_post=join_team,
                hx_swap="none",
            )
            if game.state == gm.StateMachine.WAITING_FOR_PLAYERS and not r in team
            else None
        ),
        id="id-" + team.id,
        hx_swap_oob="true",
        cls=f"mg-game-card mg-team-card {card_cls} {winner_classes}",
        body_cls='space-y-3 p-4',
        data_ui='team-card', data_team=team.id,
        data_active=str(team == game.active_team).lower(),
    )


def NewTeamCard():
    from ..routes import new_team

    return Card(Button("New team", hx_post=new_team, hx_swap="none"),
                cls=f'mg-game-card mg-new-team-card {card_cls} flex min-h-24 items-center justify-center',
                body_cls='p-4',
                data_ui='new-team-card')


def WinnerTag():
    return Div(
        "🏆 WINNER!",
        cls="absolute -top-4 -right-4 bg-amber-400 text-sm font-bold px-4 py-2 rounded-full shadow-lg transform rotate-6",
    )


def PotentialScore(team: gm.Team, game: gm.GameState):
    if team != game.active_team or game.state != gm.StateMachine.REVIEWING:
        return None
    score = sum(g.points for g in game.guess_log)
    return Span("(", ColoredPoints(score), ")")

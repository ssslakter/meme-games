from ..domain import AliasPlayer, AliasLobby, GameState
from ...shared import *
from ...user import *
from .game_cards import *
from .settings import *

def Game(reciever: AliasPlayer | User, state: GameState, **kwargs):
    return Div(
        GameInfo(state),
        Grid(*[TeamCard(reciever, team) for team in state.teams.values()],
             NewTeamCard() if not state.team_by_player(reciever) else None,
             cols=5),
        VoteButton(reciever, state),
        GuessPanel(reciever, state),
        id='game',
        **kwargs
        )

def Page(reciever: AliasPlayer | User, lobby: AliasLobby):
    from ..routes import ws_url
    return MainPage(
        Game(reciever, lobby.game_state),
        Spectators(reciever, lobby),
        SettingsPopover(reciever, lobby, 
                        custom_host_settings=PackSelect(lobby.game_state)),
        hx_ext="ws",
        ws_connect=ws_url,
        no_image=True,
        cls='p-10'
    )


def Spectators(reciever: AliasPlayer | User, lobby: Lobby):
    from ..routes import spectate

    return Card(
        "Spectators: ",
        Div(
            *[
                UserName(reciever, p.user, is_connected=p.is_connected)
                for p in lobby.sorted_members()
                if not p.is_player
            ],
            id="spectators",
            cls="flex flex-col gap-1",
        ),
        body_cls='p-2',
        hx_post=spectate,
        hx_swap='none',
        tabindex="0",
        cls=f"fixed right-0 top-1/3 -translate-y-1/2 rounded-r-none p-2 cursor-pointer"
    )
    
    
def JoinSpectators(r: AliasPlayer, p: AliasPlayer):
    return Div(UserName(r.user, p.user), hx_swap_oob="beforeend:#spectators")


def ActiveGameState(r: AliasPlayer | User, lobby: Lobby):
    return Spectators(r, lobby), Game(r, lobby)

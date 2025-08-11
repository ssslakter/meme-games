from ..domain import AliasPlayer, AliasLobby, GameState
from ...shared import *
from ...shared.settings import LockLobby
from ...shared.spectators import Spectators, register_lobby_spectators_update
from ...user import *
from .team import *
from .settings import *

def Game(reciever: AliasPlayer | User, state: GameState, **kwargs):
    return Div(
        Div(*[TeamCard(reciever, team, state) for team in state.teams.values()],
             NewTeamCard() if state.state==gm.StateMachine.WAITING_FOR_PLAYERS and not state.team_by_player(reciever) else None,
             cls='gap-4 flex flex-wrap justify-center'),
        WordPanel(reciever, state),
        GameControls(reciever, state),
        id='game',
        **kwargs
        )

def Page(reciever: AliasPlayer | User, lobby: AliasLobby):
    from ..routes import ws_url
    return LobbyPage(
        Game(reciever, lobby.game_state),
        Spectators(reciever, lobby),
        SettingsPopover(Div(PackSelect(lobby.game_state), 
                            ConfigLobby(reciever, lobby.game_state),
                            cls='w-full')),
        hx_ext="ws",
        ws_connect=ws_url,
        no_image=True,
        cls='p-10'
    )


def ActiveGameState(r: AliasPlayer | User, lobby: Lobby):
    return Spectators(r, lobby), Game(r, lobby)


register_lobby_spectators_update(
    AliasLobby, 
    lambda r, lobby, _: Game(r, lobby.game_state, hx_swap_oob='true')
    )
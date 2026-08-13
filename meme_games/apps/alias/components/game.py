from ..domain import GameState, ALIAS
from ...shared import *
from ...shared.settings import LockLobby
from ...shared.spectators import Spectators, register_game_view
from ...user import *
from .team import *
from .settings import *

def Game(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    state: GameState = lobby.state
    return Div(
        Div(*[TeamCard(reciever, team, state) for team in state.teams.values()],
             NewTeamCard() if state.state==gm.StateMachine.WAITING_FOR_PLAYERS and not state.team_by_player(reciever) else None,
             cls='gap-4 flex flex-wrap justify-center'),
        WordPanel(reciever, state),
        GameControls(reciever, state),
        id='game',
        cls=stringify(('mg-game mg-game-alias', kwargs.pop('cls', ''))),
        data_ui='game', data_game='alias', data_state=state.state,
        **kwargs
        )

def Page(reciever: LobbyMember | User, lobby: Lobby):
    from ..routes import ws_url
    return LobbyPage(
        Game(reciever, lobby),
        Spectators(reciever, lobby),
        SettingsPopover(Div(PackSelect(lobby.state),
                            ConfigLobby(reciever, lobby.state),
                            cls='w-full'),
                        lobby=lobby, member=reciever),
        hx_ext="ws",
        ws_connect=ws_url,
        no_image=True,
        title = f'Alias lobby: {lobby.id}',
        cls='p-10', page='alias'
    )


register_game_view(ALIAS, Game)

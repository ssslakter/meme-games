from ..domain import GameState, ALIAS
from ...shared import *
from ...shared.spectators import register_game_view
from ...user import *
from .team import *
from .settings import *

def Game(reciever: LobbyMember | User, lobby: Lobby, **kwargs: Any) -> FT:
    state: GameState = lobby.state
    playing = state.state == gm.StateMachine.ROUND_PLAYING
    return Div(
        GameRail(
            Div(
                H3('Teams'),
                Div(*[TeamCard(reciever, team, state) for team in state.teams.values()],
                    NewTeamCard() if state.state == gm.StateMachine.WAITING_FOR_PLAYERS and not state.team_by_player(reciever) else None,
                    cls='mg-team-grid flex flex-col gap-3', data_ui='team-grid'),
                GuessPanel(reciever, state) if playing else None,
                cls='mg-alias-team-content flex min-h-0 flex-col gap-4'),
            ChatPanel(reciever, lobby, cls='mg-alias-chat'),
            cls='mg-alias-teams lg:h-[calc(100vh-7rem)] lg:max-h-[calc(100vh-7rem)] lg:overflow-hidden',
            data_ui='alias-teams'),
        Div(WordPanel(reciever, state), GameControls(reciever, state),
            cls='mg-alias-stage flex min-w-0 items-start justify-center', data_ui='alias-stage'),
        id='game',
        cls=stringify(('mg-game mg-game-alias grid min-w-0 items-start gap-6 lg:grid-cols-[20rem_minmax(0,1fr)]', kwargs.pop('cls', ''))),
        data_ui='game', data_game='alias', data_state=state.state,
        **kwargs
        )

def Page(reciever: LobbyMember | User, lobby: Lobby) -> Any:
    from ..routes import ws_url
    return (*LobbyPage(
        GameShell(
            Game(reciever, lobby),
            LobbyTools(reciever, lobby,
                       Div(HostGameActions(reciever, lobby.state), PackSelectButton(),
                           ConfigLobby(reciever, lobby.state), cls='w-full space-y-6'),
                       show_chat=False)),
        hx_ext="ws",
        ws_connect=ws_url,
        no_image=True,
        user=reciever,
        title = f'Alias lobby: {lobby.id}',
        page='alias'
    ), PackSelectModal(lobby.state), RestartConfirmation())


register_game_view(ALIAS, Game)

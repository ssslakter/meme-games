from meme_games.core import *
from meme_games.domain import *
from ..shared.components import *

lobby_service = DI.get(LobbyService)


def LobbyInfo(lobby: Lobby):
    print(dt.datetime.now() - (lobby.last_active + lobby_service.lobby_lifetime))
    return Div(f'{lobby.id}: ',
               A('join', href=f'/whoami/{lobby.id}', hx_boost='false'),
               f'Last active: {lobby.last_active.strftime("%Y-%m-%d %H:%M:%S")}',
               Div("Will be deleted in: ", Timer(lobby.last_active + lobby_service.lobby_lifetime - dt.datetime.now())),
               style='display: flex; gap: 8px;')


@rt
def monitor():
    lobbies_list = Div(H3("Who am I lobbies:"), Ul(*[Li(LobbyInfo(lobby)) for lobby in lobby_service.lobbies.values()]),
                       _='init updateTimer() then setInterval(updateTimer, 500)')
    return Titled("Current active lobbies",
                  lobbies_list if len(lobby_service.lobbies) else Div("No active lobbies"))

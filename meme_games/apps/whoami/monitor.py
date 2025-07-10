from meme_games.core import *
from meme_games.domain import *
from ..shared import *

lobby_service = DI.get(LobbyService)


def LobbyInfo(lobby: Lobby):
    return Panel(f'{lobby.id}: ',
               A('join', href=f'/whoami/{lobby.id}', hx_boost='false', cls='bg-blue-500 text-white p-2 rounded-lg hover:bg-blue-600 transition duration-150 ease-in-out'),
               f'Last active: {lobby.last_active.strftime("%Y-%m-%d %H:%M:%S")}',
               Div("Will be deleted in: ", Timer(lobby.last_active + lobby_service.lobby_lifetime - dt.datetime.now())),
               cls='flex flex-col md:flex-row items-start md:items-center justify-between p-4 space-y-2 md:space-y-0',
               style='gap: 8px;')


@settings_rt
def monitor():
    lobbies_list = Div(H3("Who am I lobbies:"),
                       Div(Ul(*[Li(LobbyInfo(lobby)) for lobby in lobby_service.lobbies.values()]), cls='space-y-4 p-4'),
                       _='init updateTimer() then setInterval(updateTimer, 500)',
                       cls='bg-white/70 dark:bg-gray-800/70 rounded-lg shadow-xl p-6')
    return MainPage("Current active lobbies",
                  lobbies_list if len(lobby_service.lobbies) else Div("No active lobbies", cls='text-center text-gray-500 dark:text-gray-400 text-lg p-6'),
                  no_image=True,
                  cls='pt-10 flex flex-col items-center justify-center min-h-screen bg-gray-100 dark:bg-gray-900')

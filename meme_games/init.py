from fasthtml.common import *

from meme_games.user import UserManager
from meme_games.lobby import LobbyManager

def init_services(db: Database):
    return UserManager(db), LobbyManager()
    

hdrs = [
    Script(src="https://unpkg.com/hyperscript.org@0.9.13"),
    Link(rel="stylesheet", href="https://fonts.googleapis.com/icon?family=Material+Icons"),
    Style('''
          .settings:hover {
              background-color: lightgreen;
              cursor: pointer;
          }''')
]
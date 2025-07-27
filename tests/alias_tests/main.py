from tests.client import TestWebClient
from meme_games.apps.alias.routes import *
from httpx import Cookies

url = "http://localhost:8000/alias" 
ws_url = "ws://localhost:8000/ws/alias"
lobby_name = 'test'
with TestWebClient(url) as client:
    client.get(f"/{lobby_name}")
    print(client.cli.headers)
    client.connect_ws(ws_url)
    client.post(join_team.to(team_id='1'))
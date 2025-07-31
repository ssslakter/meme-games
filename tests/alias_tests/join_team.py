from tests.client import TestWebClient
from itertools import repeat
from meme_games.apps.user.routes import edit_name
import meme_games.apps.alias.routes as alias


client_idx = 0

def join_team(client, team_id):
    global client_idx
    client.post(edit_name.to(name=f'client {client_idx}'))
    client.get(alias.index.to(lobby_id=lobby_name))
    client.connect_ws(ws_url)
    client.post(alias.join_team.to(team_id=team_id))

def new_team(client):
    global client_idx
    client.post(edit_name.to(name=f'client {client_idx}'))
    client.get(alias.index.to(lobby_id=lobby_name))
    client.connect_ws(ws_url)
    client.post(alias.new_team.to())


url = "http://localhost:8000" 
ws_url = "ws://localhost:8000/ws/alias"
lobby_name = '54c4d'
timeout= 10000000
n_clients = 3

with TestWebClient(url, timeout) as client:
    new_team(client)
    res = client.get(alias.get_teams.to()).json()
    team_ids = res['team_ids']

for _, id in zip(range(n_clients), repeat(team_ids[-1])):
    client_idx += 1
    with TestWebClient(url, timeout) as cli:
        new_team(cli)
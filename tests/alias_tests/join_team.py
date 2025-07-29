from tests.client import TestWebClient
from itertools import cycle
from meme_games.apps.user.routes import edit_name
import meme_games.apps.alias.routes as alias


client_idx = 0

def join_team(team_id):
    global client_idx
    with TestWebClient(url, timeout) as client:
        res = client.post(edit_name.to(name=f'client {client_idx}'))
        print(res)
        print("aaaa")
        print(alias.index.to(lobby_id=lobby_name))
        client.get(alias.index.to(lobby_id=lobby_name))
        client.connect_ws(ws_url)
        client.post(alias.join_team.to(team_id=team_id))


url = "http://localhost:8000" 
ws_url = "ws://localhost:8000/ws/alias"
lobby_name = 'test'
timeout= 10000000
n_clients = 3

with TestWebClient(url, timeout) as client:
    res = client.post(edit_name.to(name=f'client {client_idx}'))
    client.get(alias.index.to(lobby_id=lobby_name))
    client.connect_ws(ws_url)
    client.post(alias.new_team.to())
    res = client.get(alias.get_teams.to()).json()
    team_ids = res['team_ids']

for _, id in zip(range(n_clients), cycle(team_ids)):
    client_idx += 1
    join_team(id)
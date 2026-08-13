"""Route registration order: action paths must not be swallowed by /{lobby_id}."""
from starlette.testclient import TestClient
from meme_games.core import DI
from meme_games.domain import LobbyService
from meme_games.main import app

service = DI.get(LobbyService)

ACTION_PATHS = ['/alias/vote', '/alias/guess', '/alias/start_game', '/whoami/play', '/whoami/notes']


def test_action_routes_do_not_create_lobbies():
    with TestClient(app, client=("10.0.0.1", 1), raise_server_exceptions=False) as c:
        before = set(service.lobbies)
        for path in ACTION_PATHS:
            c.get(path, follow_redirects=False)
        assert set(service.lobbies) == before, f'action GETs created {set(service.lobbies) - before}'


def test_lobby_route_still_works():
    with TestClient(app, client=("10.0.0.2", 1)) as c:
        assert c.get('/alias/abc12', headers={'user-agent': 'Mozilla/5.0 Firefox'}).status_code == 200
        assert 'abc12' in service.lobbies


def test_no_route_shadows_a_later_one():
    """A parameterised path registered before a literal sibling shadows it."""
    seen_param_prefixes = []
    for route in app.router.routes:
        path = getattr(route, 'path', '')
        if '{' in path:
            seen_param_prefixes.append(path[:path.index('{')])
        else:
            shadowing = [p for p in seen_param_prefixes if path.startswith(p) and '/' not in path[len(p):]]
            assert not shadowing, f'{path} is shadowed by {shadowing}'

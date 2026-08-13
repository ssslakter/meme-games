"""Route registration order: action paths must not be swallowed by /{lobby_id}."""
from starlette.testclient import TestClient
from meme_games.core import DI
from meme_games.domain import LobbyService
from meme_games.main import app
from meme_games.apps.alias.domain.game import StateMachine

service = DI.get(LobbyService)

ACTION_PATHS = ['/alias/vote', '/alias/guess', '/alias/start_game', '/whoami/play', '/whoami/notes',
                '/codenames/join_team', '/codenames/start_game', '/codenames/reveal_card']


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


def test_alias_joining_another_team_removes_the_old_membership():
    headers = {'user-agent': 'Mozilla/5.0 Firefox'}
    with TestClient(app, client=("10.0.0.3", 1)) as host, TestClient(app, client=("10.0.0.4", 1)) as guest:
        host.get('/alias/team-move', headers=headers)
        host.post('/alias/new_team', headers=headers)
        guest.get('/alias/team-move', headers=headers)
        guest.post('/alias/new_team', headers=headers)
        lobby = service.lobbies['team-move']
        guest_member = next(member for member in lobby.members.values() if member != lobby.host)
        target = lobby.state.team_by_player(guest_member)

        host.post(f'/alias/join_team?team_id={target.id}', headers=headers)

        memberships = [team for team in lobby.state.teams.values() if lobby.host in team]
        assert memberships == [target]


def test_alias_host_can_pause_resume_and_restart_without_losing_teams():
    headers = {'user-agent': 'Mozilla/5.0 Firefox'}
    with TestClient(app, client=("10.0.0.5", 1)) as host:
        host.get('/alias/host-actions', headers=headers)
        lobby = service.lobbies['host-actions']
        member = lobby.host
        member.play()
        team = lobby.state.create_team()
        team.append(member)
        team.points = 8
        lobby.state.state = StateMachine.ROUND_PLAYING
        lobby.state.active_team = team
        lobby.state.active_player = member
        lobby.state.active_word = 'apple'
        lobby.state.timer.set(30)

        host.post('/alias/pause_game', headers=headers)
        assert lobby.state.timer.paused
        host.post('/alias/pause_game', headers=headers)
        assert not lobby.state.timer.paused
        host.post('/alias/restart_game', headers=headers)

        assert lobby.state.state == StateMachine.WAITING_FOR_PLAYERS
        assert lobby.state.team_by_player(member) is team
        assert team.points == 0


def test_pages_are_never_served_from_the_browser_cache():
    """A cached page replays state the server has moved past, e.g. a nickname prompt
    for a user who has since been named."""
    with TestClient(app, client=("10.0.0.3", 1)) as c:
        page = c.get('/whoami/cache1', headers={'user-agent': 'Mozilla/5.0 Firefox'})
        assert page.headers['cache-control'] == 'no-store'


def test_static_files_keep_their_own_caching():
    with TestClient(app, client=("10.0.0.4", 1)) as c:
        css = c.get('/static/styles/app.css')
        assert css.status_code == 200
        assert 'max-age' in css.headers['cache-control']

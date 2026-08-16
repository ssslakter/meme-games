"""The host switches the game; everyone stays in the same lobby and follows along."""
from starlette.testclient import TestClient

from meme_games.core import DI
from meme_games.domain import LobbyService
from meme_games.main import app
from meme_games.apps.whoami.domain import WHOAMI
from meme_games.apps.alias.domain import ALIAS

service = DI.get(LobbyService)
BROWSER = {'user-agent': 'Mozilla/5.0 Firefox'}


def _client(ip): return TestClient(app, client=(ip, 1), raise_server_exceptions=False)


def test_goto_carries_the_navigation_on_a_child():
    from fasthtml.common import to_xml
    from meme_games.apps.shared.settings import GoTo

    markup = to_xml(GoTo('/alias/x'))

    # a childless beforeend carrier is read as an empty template and inserts nothing
    assert '<div' in markup.split('>', 1)[1], 'the navigating element must be a child of the carrier'
    assert 'go to url "/alias/x"' in markup


def test_host_switch_keeps_the_lobby_and_the_other_games_state():
    with _client('172.16.0.1') as host:
        host.get('/whoami/sw-a', headers=BROWSER)
        lobby = service.lobbies['sw-a']
        lobby.host.play()
        lobby.lock()
        lobby.state.player(lobby.host.uid).set_notes('still here')

        r = host.post('/switch_game?game=' + ALIAS, headers=BROWSER, follow_redirects=False)

        assert r.status_code == 303
        assert dict(r.headers)['location'] == '/alias/sw-a'
        assert lobby.current_game == ALIAS
        assert not lobby.host.is_player
        assert not lobby.locked
        assert lobby.states[WHOAMI].player(lobby.host.uid).notes == 'still here'


def test_stale_game_url_redirects_without_switching_lobby():
    with _client('172.16.0.6') as host:
        host.get('/whoami/sw-d', headers=BROWSER)
        lobby = service.lobbies['sw-d']

        stale = host.get('/alias/sw-d', headers=BROWSER, follow_redirects=False)

        assert stale.status_code == 303
        assert dict(stale.headers)['location'] == '/whoami/sw-d'
        assert lobby.current_game == WHOAMI


def test_only_the_host_may_switch():
    with _client('172.16.0.2') as host, _client('172.16.0.3') as guest:
        host.get('/whoami/sw-b', headers=BROWSER)
        page = guest.get('/whoami/sw-b', headers=BROWSER).text
        assert 'Switch game' not in page, 'only the host gets the control'

        guest.post('/switch_game?game=' + ALIAS, headers=BROWSER, follow_redirects=False)
        assert service.lobbies['sw-b'].current_game == WHOAMI


def test_connected_members_are_sent_to_the_new_game():
    with _client('172.16.0.4') as host, _client('172.16.0.5') as guest:
        host.get('/whoami/sw-c', headers=BROWSER)
        guest.get('/whoami/sw-c', headers=BROWSER)
        host.post('/whoami/play', headers=BROWSER)
        guest.post('/whoami/play', headers=BROWSER)
        with guest.websocket_connect('/ws/whoami') as ws:
            ws.receive_text()  # initial board
            host.post('/switch_game?game=' + ALIAS, headers=BROWSER, follow_redirects=False)
            assert '/alias/sw-c' in ws.receive_text()
        assert all(not member.is_player for member in service.lobbies['sw-c'].members.values())

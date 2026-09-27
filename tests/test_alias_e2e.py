"""End-to-end Alias: every player is a separate browser session that drives the real
routes over HTTP, listens on the real lobby websocket, and keeps the DOM its tab would
show by applying OOB swaps the way htmx does. At each checkpoint that live DOM must
equal a fresh page load, so an incremental update can never render differently from
a full one, and every receiver must see the round laid out the same way."""
import time
import anyio
import pytest
from bs4 import BeautifulSoup, NavigableString, Tag
from starlette.testclient import TestClient

from meme_games.core import DI
from meme_games.domain import LobbyService
from meme_games.main import app
from meme_games.apps.alias.domain.game import StateMachine

service = DI.get(LobbyService)
BROWSER = {'user-agent': 'Mozilla/5.0 Chrome/120'}
HX = {**BROWSER, 'HX-Request': 'true'}
SETTINGS = dict(time_limit='60', word_collection_time='60', max_score='40', max_teams='4')


def apply_oob(dom: BeautifulSoup, html: str, default: str | None) -> list[str]:
    '''Swap the top-level OOB elements of a response into `dom`. The ws extension treats
    every top-level element as `hx-swap-oob="true"`; plain HTTP responses only swap marked ones.
    Returns the ids htmx would report as missing targets.'''
    missing = []
    for el in BeautifulSoup(html, 'html.parser').find_all(recursive=False):
        how = el.get('hx-swap-oob', default)
        if how is None: continue
        style, _, selector = how.partition(':')
        if style in ('true', 'outerHTML'):
            if not el.get('id'): continue
            target = dom.find(id=el['id'])
            if target is None: missing.append(el.get('id')); continue
            target.replace_with(el)
            continue
        target = dom.select_one(selector)
        if target is None: missing.append(selector); continue
        if style == 'beforeend': target.append(el)
        elif style == 'innerHTML':
            target.clear()
            target.extend(list(el.children))
    return missing


def canon(node, depth: int = 0) -> list[str]:
    '''Indentation-insensitive, timer-insensitive outline of a subtree, one node per line.'''
    if isinstance(node, NavigableString):
        text = ' '.join(node.split())
        return [f'{"  " * depth}"{text}"'] if text and type(node) is NavigableString else []
    if not isinstance(node, Tag): return []
    if node.get('data-ui') == 'timer': return [f'{"  " * depth}<timer>']
    attrs = ' '.join(f'{k}="{" ".join(v) if isinstance(v, list) else v}"'
                     for k, v in sorted(node.attrs.items()) if k != 'hx-swap-oob')
    lines = [f'{"  " * depth}<{node.name} {attrs}>']
    for child in node.children: lines += canon(child, depth + 1)
    return lines


def region(el: Tag) -> str:
    if el.find_parent(attrs={'data-ui': 'alias-teams'}): return 'rail'
    if el.find_parent(attrs={'data-ui': 'alias-stage'}): return 'stage'
    return 'elsewhere'


class Tab:
    '''One player's browser tab: own cookie jar, a live websocket and the DOM it shows.'''

    def __init__(self, server: TestClient, lobby_id: str, name: str):
        self.http = TestClient(app, headers=BROWSER)
        self.http.portal = server.portal  # every tab talks to the same server process
        self.lobby_id, self.name, self.missing = lobby_id, name, []
        self.http.put('/me/name', data={'name': name})
        self.dom = self.load()
        self.ws = self.http.websocket_connect('/ws/alias').__enter__()
        self.pump()

    @property
    def lobby(self): return service.lobbies[self.lobby_id]

    @property
    def member(self): return next(m for m in self.lobby.members.values() if m.name == self.name)

    def load(self) -> BeautifulSoup:
        page = self.http.get(f'/alias/{self.lobby_id}')
        assert page.status_code == 200
        return BeautifulSoup(page.text, 'html.parser')

    def pump(self, quiet: float = 0.02) -> None:
        async def next_message():
            with anyio.move_on_after(quiet): return await self.ws._send_rx.receive()
        while (message := self.ws.portal.call(next_message)) is not None:
            if 'text' in message: self.missing += apply_oob(self.dom, message['text'], default='true')

    def post(self, url: str, **data) -> str:
        response = self.http.post(url, headers=HX, data=data)
        assert response.status_code == 200, response.text
        self.pump()
        self.missing += apply_oob(self.dom, response.text, default=None)
        return response.text

    def close(self) -> None: self.ws.__exit__(None, None, None)

    # --- what the player sees ---
    def board(self) -> list[str]: return canon(self.dom.select_one('#game'))
    def fresh_board(self) -> list[str]: return canon(self.load().select_one('#game'))

    def layout(self) -> list[tuple[str, str]]:
        return [(el['data-ui'], region(el)) for el in
                self.dom.select('#game [data-ui="round-center"], #game [data-ui="round-history"]')]

    def words(self) -> list[str]:
        return [el.get_text(strip=True) for el in self.dom.select('#guess_log [data-ui="word-text"]')]

    def count(self) -> int: return int(self.dom.select_one('#guess_count').get_text())
    def phase(self) -> str: return self.dom.select_one('[data-ui="round-status"]')['data-phase']

    def form(self, **toggles: bool) -> dict:
        '''Serialise the host settings form like a browser, flipping the named checkboxes.'''
        data = {}
        for el in self.dom.select('#alias-config form input'):
            name = el.get('name')
            if not name or el.has_attr('disabled'): continue
            if el.get('type') == 'checkbox':
                if toggles.get(name, el.has_attr('checked')): data[name] = 'on'
            else: data[name] = el.get('value', '')
        return data

    def checkbox(self, id: str) -> tuple[bool, bool]:
        box = self.dom.select_one(f'#alias-config #{id}')
        return box.has_attr('checked'), box.has_attr('disabled')


class Table:
    '''A lobby with a host and guests, all on one server.'''

    def __init__(self, server: TestClient, lobby_id: str, names: list[str]):
        self.server, self.lobby_id = server, lobby_id
        self.tabs = [Tab(server, lobby_id, name) for name in names]
        for tab in self.tabs: tab.pump()

    @property
    def host(self) -> Tab: return self.tabs[0]
    @property
    def game(self): return service.lobbies[self.lobby_id].state

    def tab(self, member) -> Tab: return next(t for t in self.tabs if t.name == member.name)
    def pump(self) -> None:
        for tab in self.tabs: tab.pump()

    def one_team(self, *names: str) -> None:
        self.tab_named(names[0]).post('/alias/new_team')
        team_id = next(iter(self.game.teams))
        for name in names[1:]: self.tab_named(name).post('/alias/join_team', team_id=team_id)
        self.pump()

    def tab_named(self, name: str) -> Tab: return next(t for t in self.tabs if t.name == name)

    def wait(self, cond, timeout: float = 3) -> None:
        deadline = time.monotonic() + timeout
        while not cond():
            assert time.monotonic() < deadline, 'server never reached the expected state'
            self.server.portal.call(anyio.sleep, 0.05)

    def expire_timer(self) -> None:
        '''Run the real timeout path without waiting out the clock.'''
        self.game.timer.rem_t = 0
        self.wait(lambda: self.game.timer.finished or self.game.state != StateMachine.ROUND_PLAYING)
        self.server.portal.call(anyio.sleep, 0.1)
        self.pump()

    def ready_and_start(self) -> Tab:
        for member in list(self.game.active_team.members): self.tab(member).post('/alias/vote', voted='true')
        explainer = self.tab(self.game.active_player)
        explainer.post('/alias/start_round')
        self.pump()
        return explainer

    def assert_in_sync(self) -> None:
        for tab in self.tabs:
            assert tab.board() == tab.fresh_board(), f'{tab.name} sees a board a reload would not show'

    def assert_one_layout(self) -> None:
        for tab in self.tabs:
            assert tab.layout() == [('round-center', 'stage'), ('round-history', 'stage')], tab.name

    def close(self) -> None:
        for tab in self.tabs: tab.close()


@pytest.fixture
def server():
    with TestClient(app, headers=BROWSER) as client:
        tables: list[Table] = []
        client.table = lambda lobby_id, names: tables.append(Table(client, lobby_id, names)) or tables[-1]
        try: yield client
        finally:
            # an open test websocket keeps the portal alive and the teardown would hang
            for table in tables: table.close()


@pytest.mark.parametrize('hide', [False, True])
def test_wordpack_round_looks_the_same_to_everyone(server, hide):
    table = server.table(f'e2e-pack-{hide}', ['Alice', 'Bob', 'Carol', 'Dave'])
    table.one_team('Alice', 'Bob', 'Carol')
    host = table.host
    host.post('/alias/update_settings', **SETTINGS, **({'hide_skipped_words': 'on'} if hide else {}))
    host.post('/alias/start_game')
    table.pump()
    assert not table.tab_named('Dave').member.is_player

    explainer = table.ready_and_start()
    assert table.game.state == StateMachine.ROUND_PLAYING
    table.assert_one_layout()
    table.assert_in_sync()

    said = []
    for correct in (True, False, True):
        said.append(table.game.active_word)
        explainer.post('/alias/guess', correct=str(correct))
    table.pump()
    guessed, skipped = [said[2], said[0]], said[1]

    for tab in table.tabs:
        sees_skip = tab is explainer or not hide
        expected = [said[2], skipped, said[0]] if sees_skip else guessed
        assert tab.words() == expected, tab.name
        assert tab.count() == len(expected), tab.name
    table.assert_one_layout()
    table.assert_in_sync()

    table.expire_timer()
    assert table.game.state == StateMachine.ROUND_PLAYING
    assert {tab.phase() for tab in table.tabs} == {'last-word'}
    table.assert_in_sync()

    said.append(table.game.active_word)
    explainer.post('/alias/guess', correct='True')
    table.pump()
    assert table.game.state == StateMachine.REVIEWING
    table.assert_one_layout()
    table.assert_in_sync()
    for tab in table.tabs:
        assert (skipped in tab.words()) == (tab is explainer or not hide), tab.name
        assert tab.dom.select('#guess_log [data-ui="word-entry"] button'), 'review exposes score controls'

    skipped_id = next(g.id for g in table.game.guess_log if g.word == skipped)
    guessed_id = next(g.id for g in table.game.guess_log if g.word == said[0])
    for tab in table.tabs: tab.missing.clear()
    explainer.post('/alias/change_guess_points', guess_id=skipped_id, delta='-1')
    table.tab_named('Carol' if explainer.name != 'Carol' else 'Bob').post(
        '/alias/change_guess_points', guess_id=guessed_id, delta='1')
    table.pump()
    table.assert_in_sync()
    assert all(not tab.missing for tab in table.tabs), {t.name: t.missing for t in table.tabs}

    first_explainer = explainer.name
    for member in list(table.game.active_team.members): table.tab(member).post('/alias/vote', voted='true')
    table.pump()
    assert table.game.state == StateMachine.VOTING_TO_START
    table.assert_in_sync()

    explainer = table.ready_and_start()
    assert explainer.name != first_explainer
    table.assert_one_layout()
    table.assert_in_sync()
    assert all(tab.words() == [] and tab.count() == 0 for tab in table.tabs)


def test_settings_form_is_the_single_source_of_truth(server):
    table = server.table('e2e-settings', ['Host', 'Guest'])
    table.one_team('Host', 'Guest')
    host, guest = table.tabs

    host.post('/alias/update_settings', **host.form(player_words=True))
    assert table.game.config.player_words and not table.game.config.hide_skipped_words
    assert host.checkbox('hide-skipped-words') == (True, True)

    host.post('/alias/update_settings', **host.form(player_words=False))
    assert not table.game.hides_skipped_words()
    assert host.checkbox('hide-skipped-words') == (False, False)

    host.post('/alias/update_settings', **host.form(hide_skipped_words=True))
    host.post('/alias/update_settings', **host.form(player_words=True))
    host.post('/alias/update_settings', **host.form(player_words=False))
    assert table.game.config.hide_skipped_words
    assert host.checkbox('hide-skipped-words') == (True, False)

    host.post('/alias/update_settings', **host.form(player_words=True, disable_skip=True))
    host.post('/alias/start_game')
    assert table.game.state == StateMachine.COLLECTING_WORDS
    host.post('/alias/update_settings', **{**host.form(), 'player_words': ''})
    assert table.game.config.player_words, 'the word source cannot change mid-game'
    assert host.checkbox('player-words') == (True, True)
    table.pump()
    assert guest.board() == guest.fresh_board()


def test_player_words_round_keeps_skips_private_and_ends_on_the_timer(server):
    table = server.table('e2e-player-words', ['Ann', 'Ben', 'Cat'])
    table.one_team('Ann', 'Ben', 'Cat')
    host = table.host
    host.post('/alias/update_settings', **host.form(player_words=True))
    host.post('/alias/start_game')
    table.pump()
    for tab, words in zip(table.tabs, ['apple\npear', 'plum\nfig', 'kiwi']):
        tab.post('/alias/submit_words', words=words, finalized='True')
    table.expire_timer()
    table.wait(lambda: table.game.state == StateMachine.VOTING_TO_START)
    table.pump()
    table.assert_in_sync()

    explainer = table.ready_and_start()
    table.assert_one_layout()
    skipped = table.game.active_word
    explainer.post('/alias/guess', correct='False')
    guessed = table.game.active_word
    explainer.post('/alias/guess', correct='True')
    on_screen = table.game.active_word
    table.pump()
    for tab in table.tabs:
        assert tab.words() == ([guessed, skipped] if tab is explainer else [guessed]), tab.name
    table.assert_in_sync()

    table.expire_timer()
    assert table.game.state == StateMachine.REVIEWING, 'no last word unless the setting asks for it'
    assert on_screen in table.game.word_pool
    table.assert_one_layout()
    table.assert_in_sync()
    for tab in table.tabs:
        assert (skipped in tab.words()) == (tab is explainer), tab.name


def test_disabled_skip_is_enforced_for_the_explainer(server):
    table = server.table('e2e-no-skip', ['Eve', 'Fay'])
    table.one_team('Eve', 'Fay')
    table.host.post('/alias/update_settings', **table.host.form(disable_skip=True))
    table.host.post('/alias/start_game')
    explainer = table.ready_and_start()

    assert '>Skip<' not in str(explainer.dom.select_one('#game'))
    word = table.game.active_word
    explainer.post('/alias/guess', correct='False')
    assert table.game.active_word == word and table.game.guess_log == []
    table.pump()
    table.assert_in_sync()

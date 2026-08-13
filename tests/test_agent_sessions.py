import os
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

from fasthtml.common import to_xml

from meme_games.apps.codenames.domain import CODENAMES
from meme_games.apps.shared.settings import AllowAgents
from meme_games.apps.shared.utils import new_lobby_options
from meme_games.core import DI
from meme_games.domain import AgentPlayerSessionService, LobbyService, UserManager


lobbies = DI.get(LobbyService)
users = DI.get(UserManager)
sessions = DI.get(AgentPlayerSessionService)


def test_player_handles_are_hashed_and_expire_with_lobby():
    lobby = lobbies.create_lobby(users.create(name='host'), 'session-delete', CODENAMES)
    session, handle = sessions.create(lobby.id, 'Robot')
    assert handle not in session.handle_hash and sessions.get(handle) == session
    lobbies.delete_lobby(lobby.id)
    assert sessions.get(handle) is None
    assert sessions.get('mgai_retired_invite_token') is None


def test_agent_preference_only_initializes_new_lobbies():
    req = SimpleNamespace(query_params={'allow_agents': '1'})
    host = users.create(name='preference-host')
    created, was_created = lobbies.get_or_create(
        host, 'preference-lobby', CODENAMES, **new_lobby_options(req))
    assert was_created and created.allow_agents
    existing, was_created = lobbies.get_or_create(
        host, created.id, CODENAMES, allow_agents=False)
    assert not was_created and existing.allow_agents


def test_allow_agents_control_does_not_overwrite_preference_until_changed():
    lobby = lobbies.create_lobby(users.create(name='settings-host'), 'agent-setting', CODENAMES)
    initial = to_xml(AllowAgents(lobby))
    changed = to_xml(AllowAgents(lobby, save_preference=True))
    assert 'Allow agents to join' in initial and 'localStorage.setItem' not in initial
    assert 'localStorage.setItem' in changed


def test_existing_database_gets_session_related_columns(tmp_path):
    path = tmp_path / 'old.db'
    connection = sqlite3.connect(path)
    connection.execute(
        'CREATE TABLE lobbies (id TEXT PRIMARY KEY, locked INTEGER, last_active TEXT, '
        'current_game TEXT, states_json TEXT, persistent INTEGER)')
    connection.execute('CREATE TABLE user (uid TEXT PRIMARY KEY, name TEXT, avatar TEXT, named INTEGER)')
    connection.commit()
    connection.close()
    code = """
from meme_games.main import app
from meme_games.services import db
lobby_columns = {row['name'] for row in db.q('pragma table_info(lobbies)')}
user_columns = {row['name'] for row in db.q('pragma table_info(user)')}
assert {'revision', 'allow_agents'} <= lobby_columns
assert 'kind' in user_columns
assert 'agent_player_sessions' in db.t
"""
    subprocess.run([sys.executable, '-c', code], check=True,
                   env={**os.environ, 'DB_PATH': str(path)})

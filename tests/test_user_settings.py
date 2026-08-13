import re
from pathlib import Path

from starlette.testclient import TestClient

from meme_games.main import app


HEADERS = {'user-agent': 'Mozilla/5.0 Firefox'}


def test_user_settings_page_and_nickname_update():
    with TestClient(app, client=('10.0.1.1', 1)) as client:
        page = client.get('/me/', headers=HEADERS)
        assert page.status_code == 200
        assert 'data-page="settings"' in page.text
        assert 'id="identity-settings"' in page.text
        assert 'id="custom-css-editor"' in page.text
        assert 'id="custom-css-enabled"' in page.text

        updated = client.put('/me/name', data={'name': '  Theme   Maker  '}, headers=HEADERS)
        assert updated.status_code == 200
        assert 'Theme Maker' in updated.text


def test_avatar_can_be_uploaded_and_removed_from_settings():
    with TestClient(app, client=('10.0.1.2', 1)) as client:
        client.get('/me/', headers=HEADERS)
        uploaded = client.post(
            '/me/avatar',
            files={'file': ('avatar.png', b'avatar', 'image/png')},
            headers=HEADERS,
        )
        match = re.search(r'/user-content/([^"?]+\.png)', uploaded.text)
        assert uploaded.status_code == 200 and match
        avatar_path = Path('user-content') / match.group(1)
        try:
            assert avatar_path.exists()
        finally:
            removed = client.delete('/me/avatar', headers=HEADERS)
        assert removed.status_code == 200
        assert not avatar_path.exists()


def test_lobby_settings_no_longer_edit_identity():
    with TestClient(app, client=('10.0.1.3', 1)) as client:
        alias = client.get('/alias/settings-test', headers=HEADERS)
        whoami = client.get('/whoami/settings-test', headers=HEADERS)
        assert 'Lobby actions' in alias.text
        assert 'Save nickname' not in alias.text
        assert 'accept="image/*"' not in alias.text
        assert 'accept="image/*"' not in whoami.text

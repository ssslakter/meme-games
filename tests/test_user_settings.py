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
        assert 'Cyberpunk 2077' in page.text
        assert 'Sakura' in page.text
        assert 'id="custom-css-template"' in page.text
        assert 'onsubmit=' not in page.text
        assert 'fixed top-0 left-0 right-0' in page.text
        assert '-translate-y-[calc(100%-1rem)]' not in page.text

        updated = client.put('/me/name', data={'name': '  Theme   Maker  '}, headers=HEADERS)
        assert updated.status_code == 200
        assert 'Theme Maker' in updated.text


def test_custom_css_templates_are_plain_editable_stylesheets():
    for filename in ('cyberpunk-2077.css', 'sakura.css'):
        css = Path('static/styles/themes', filename).read_text()
        assert '@import' not in css.lower()
        assert '.mg-navbar' in css
        assert 'html:not(.dark)' in css
        assert 'html.dark' in css

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
        assert '/background' not in alias.text
        assert '>Background<' not in alias.text
        assert 'Save nickname' not in alias.text
        assert 'accept="image/*"' not in alias.text
        assert 'accept="image/*"' not in whoami.text
        for page in (alias.text, whoami.text):
            assert 'data-ui="game-shell"' in page
            assert 'mg-page-content px-4 py-6 sm:px-6 lg:px-8' in page
            assert 'data-ui="settings-panel"' in page
            assert 'data-ui="leave-lobby"' in page
            assert 'data-uk-offcanvas' not in page
            assert 'settings-panel-wrapper' not in page

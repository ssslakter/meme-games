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
        assert 'id="profile-form"' in page.text
        assert 'id="avatar-file-name"' in page.text
        assert 'Selector reference and starter CSS' not in page.text
        assert 'Stable hooks' not in page.text
        assert page.text.count('>Save changes<') == 1
        assert 'Save CSS' not in page.text
        assert '>Upload<' not in page.text
        assert 'fixed top-0 left-0 right-0' in page.text
        assert '-translate-y-[calc(100%-1rem)]' not in page.text

        updated = client.put('/me/name', data={'name': '  Theme   Maker  '}, headers=HEADERS)
        assert updated.status_code == 200
        assert 'Theme Maker' in updated.text


def _offered_themes() -> list[str]:
    '''Every theme the settings page offers, so a new one cannot skip these checks.'''
    from fasthtml.common import to_xml
    from meme_games.apps.user.components.general import CustomCssSettings
    return re.findall(r'value="(/static/styles/themes/[^"]+\.css)"', to_xml(CustomCssSettings()))


def test_custom_css_templates_are_plain_editable_stylesheets():
    paths = _offered_themes()
    assert len(paths) >= 4
    for path in paths:
        css = Path(path.lstrip('/')).read_text()
        assert '@import' not in css.lower(), path
        assert '.mg-navbar' in css, path
        assert 'html:not(.dark)' in css and 'html.dark' in css, path
        # both modes must set the ink, or a theme reads as blank text on its own card
        assert css.count('--card-foreground') >= 2, path


def test_themes_leave_the_codenames_countdown_alone():
    '''The commit countdown rides .mg-word-card::after; a theme that hides its own
    corner ornament there used to take the countdown with it.'''
    for path in _offered_themes():
        css = Path(path.lstrip('/')).read_text()
        for rule in re.findall(r'[^}]*\.mg-word-card[^{}]*::after[^{]*\{[^}]*\}', css):
            if 'display: none' in rule or 'display:none' in rule:
                assert ':not([data-commit])' in rule, path

def test_single_save_updates_name_and_avatar_together():
    with TestClient(app, client=('10.0.1.2', 1)) as client:
        client.get('/me/', headers=HEADERS)
        uploaded = client.post(
            '/me/profile',
            data={'name': '  Theme   Maker  '},
            files={'file': ('avatar.png', b'avatar', 'image/png')},
            headers=HEADERS,
        )
        assert 'Theme Maker' in uploaded.text
        match = re.search(r'/user-content/([^"?]+\.png)', uploaded.text)
        assert uploaded.status_code == 200 and match
        avatar_path = Path('user-content') / match.group(1)
        try:
            assert avatar_path.exists()
            renamed = client.post('/me/profile', data={'name': 'Just Renamed'}, headers=HEADERS)
            assert 'Just Renamed' in renamed.text
            assert match.group(1) in renamed.text
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

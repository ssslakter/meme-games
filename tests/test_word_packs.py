from starlette.testclient import TestClient

from meme_games.apps.word_packs.domain import WordPackRepo
from meme_games.apps.word_packs.routes import words_from_upload
from meme_games.core import DI
from meme_games.main import app

HEADERS = {'user-agent': 'Mozilla/5.0 Firefox', 'HX-Request': 'true'}
BROWSER = {'user-agent': 'Mozilla/5.0 Firefox'}


def test_words_from_upload_reads_common_txt_encodings():
    assert words_from_upload('кот\nпёс\n'.encode('utf-8')) == 'кот\nпёс\n'
    assert words_from_upload(b'\xef\xbb\xbfapple\npear\n') == 'apple\npear\n'
    assert words_from_upload('кот\nпёс\n'.encode('cp1251')) == 'кот\nпёс\n'
    assert words_from_upload('кот\nпёс\n'.encode('utf-16')) == 'кот\nпёс\n'


def test_upload_fills_the_editor_so_the_pack_can_be_named_and_saved():
    raw = 'кот\nпёс\n'.encode('cp1251')
    with TestClient(app, client=('10.8.8.1', 1)) as client:
        client.get('/word_packs', headers=BROWSER)
        uploaded = client.post('/word_packs/upload', headers=HEADERS,
                               files={'file': ('звери.txt', raw, 'text/plain')})
        assert uploaded.status_code == 200
        assert 'name="name"' in uploaded.text and 'value="звери"' in uploaded.text
        assert 'кот' in uploaded.text and '>Save<' in uploaded.text
        assert all(p.name != 'звери' for p in DI.get(WordPackRepo).get_all())

        saved = client.post('/word_packs/save', headers=HEADERS,
                            data={'id': 'pack-zveri', 'name': 'Звери', 'words': 'кот\nпёс\n'})
        assert saved.status_code == 200
        assert 'hx-swap-oob="true"' in saved.text and 'Звери' in saved.text
        pack = DI.get(WordPackRepo).get_by_id('pack-zveri')
        assert pack.name == 'Звери' and pack.words == ['кот', 'пёс']

        # a follow-up change from clearing the file input must not replace the editor
        empty = client.post('/word_packs/upload', headers=HEADERS,
                            files={'file': ('', b'', 'application/octet-stream')})
        assert empty.status_code == 200 and 'name="words"' not in empty.text

from ..shared.utils import register_route
from .components import *

rt = APIRouter("/word_packs")
register_route(rt)

# ---------------------------------#
# ------------- Routes ------------#
# ---------------------------------#


@rt("/upload", methods=["post"])
async def upload(sess, file: UploadFile):
    text = await file.read()
    return save(sess, file.filename.split(".")[0], text.decode("utf-8"))

@rt("/delete", methods=["post"])
def delete(sess: dict, id: str):
    pack = wordpack_manager.get_by_id(id)
    if not pack or pack.author_id != sess.get('uid'):
        raise HTTPException(403, 'You can only delete your own wordpacks')
    wordpack_manager.delete(id)

@rt
def save(sess: dict, name: str, words: str, id: str = None):
    id = id or random_id()
    author = user_manager.get(sess.get('uid'))
    existing = wordpack_manager.get_by_id(id)
    if existing and existing.author_id != sess.get('uid'):
        raise HTTPException(403, 'You can only edit your own wordpacks')
    wordpack_manager.upsert(WordPack(id=id, name=name, words_=words, author_id=author.uid if author else ''))
    return WordPackEditor(hx_swap_oob='true')

@rt
def new_creation():
    return WordPackEditor(WordPack(), hx_swap_oob='true')

@rt
def index(sess: dict, pack_id: str = None):
    packs = wordpack_manager.get_all()
    wpack = wordpack_manager.get_by_id(pack_id)
    return LobbyPage(
        Container(
            Grid(
                SideBar(),
                ListCard("Wordpacks", Packs(packs, sess.get('uid')), cls='max-h-[719px] overflow-y-auto'),
                ListCard("Editor", WordPackEditor(wpack, readonly=bool(wpack and wpack.author_id != sess.get('uid')))),
                cols_sm=1,
                cols_md=3,
                cols_lg=4,
                cols_xl=5,
            ),
            cls=('pt-10', ContainerT.xl)),
            title="Word packs", no_image=True, page='word-packs')

@rt
def editor(sess: dict, id: str):
    pack = wordpack_manager.get_by_id(id)
    if pack and pack.author_id != sess.get('uid'):
        return WordPackEditor(pack, readonly=True, hx_swap_oob='true')
    return WordPackEditor(pack, hx_swap_oob='true')


@rt
def search(sess, title: str, my_only: Optional[bool] = False):
    packs = wordpack_manager.get_all()
    title = title.lower()
    # TODO do with sql query
    if my_only: packs = [p for p in packs if p.author_id==sess.get('uid')]
    if title: packs = [p for p in packs if title in p.name.lower() or title in (p.get_author_name() or '')]
    return Packs(packs, sess.get('uid'))

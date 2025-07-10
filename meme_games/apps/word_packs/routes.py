from .components import *

rt = APIRouter("/word_packs")

# ---------------------------------#
# ------------- Routes ------------#
# ---------------------------------#


@rt("/upload", methods=["post"])
async def upload(file: UploadFile):
    text = await file.read()
    wordpack_manager.insert(WordPack(name=file.filename.split(".")[0], words_=text.decode("utf-8")))
    return Packs()

@rt("/delete", methods=["post"])
def delete(id: str):
    wordpack_manager.delete(id)
    return WordPackEditor(), Div(hx_swap_oob=f"outerHTML:li:has(#{id})")

@rt
def save(name: str, words: str, id: str = None):
    id = id or random_id()
    wp = wordpack_manager.upsert(WordPack(id=id, name=name, words_=words))
    return Packs(), WordPackEditor(empty=True, hx_swap_oob='true')

@rt
def new():
    return WordPackEditor()

@rt
def index(): return Title("Word packs"),Page()

register_page("Word Packs", index.to())

@rt
def editor(id: str):
    pack = wordpack_manager.get_by_id(id)
    return WordPackEditor(pack)

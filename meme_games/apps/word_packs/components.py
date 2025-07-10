from meme_games.core import *
from .domain import *
from ..shared import *

rt = APIRouter("/word_packs")

logger = logging.getLogger(__name__)

wordpack_manager = DI.get(WordPackManager)


def WordPackRef(wp: WordPack):
    return Button(wp.name, hx_get=editor.to(id=wp.id), hx_target="#editor", style="width: 30%;", id=wp.id)


def Packs():
    return Div(id="wordpacks")(
        Ol(*[Li(WordPackRef(wp)) for wp in wordpack_manager.get_all()])
    )

def WordPackEditor(wp: WordPack = None, empty: bool = False, **kwargs):
    if empty: 
        return Div(id="editor", **kwargs)
    return Div(id="editor", **kwargs)(
        P(f"Editing {wp.name}" if wp else "New word pack"),
        Form(hx_post=save.to(), hx_target="#wordpacks")(
            Input(type="hidden", name="id", value=wp.id if wp else ""),
            Input(type="text", name="name", value=wp.name if wp else "", required=True),
            TextArea(wp.words_ if wp else "", type="text", name="words", rows=10),
            Div(
                Button("Save", type="submit", value="Save", cls="secondary"),
                Button(
                    "Delete",
                    hx_post=delete.to(id=wp.id),
                    hx_target="#editor",
                    hx_confirm=f"Are you sure to delete {wp.name}?",
                    cls="error",
                )
                if wp
                else "",
                style="display: flex; flex-direction: row; gap: 10px;",
            ),
            style="display: flex; flex-direction: column; gap: 10px; align-items: flex-start;",
        ),
    )


def MainBlock():
    return (
        Title("Word packs"),
        MainPage(
            Div(
                id="main-block",
                style="display: flex; flex-direction: row; padding: 10px; justify-content: space-around;",
            )(
                Div(
                    Div(
                        Form(hx_post=upload.to(), hx_target="#wordpacks")(
                            Input(type="file", name="file", accept="text/plain"),
                            Button(
                                "Upload", type="submit", value="Upload", cls="secondary"
                            ),
                        ),
                        Button(
                            "New", hx_get=new.to(), hx_target="#editor", cls="secondary"
                        ),
                        style="display: flex; flex-direction: row; gap: 10px; align-items: flex-start;",
                    ),
                    Packs(),
                ),
                WordPackEditor(empty=True),
            ),
            no_image=True,
            cls='pt-10'
        ),
    )


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
def index(): return MainBlock()

register_page("Word Packs", index.to())

@rt
def editor(id: str):
    pack = wordpack_manager.get_by_id(id)
    return WordPackEditor(pack)

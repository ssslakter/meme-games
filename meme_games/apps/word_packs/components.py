from meme_games.core import *
from .domain import *

rt = APIRouter("/word_packs")

logger = logging.getLogger(__name__)

wordpack_manager = DI.get(WordPackManager)


def WordPackRef(wp: WordPack):
    return Button(wp.name, hx_get=editor.to(id=wp.id), hx_target="#editor", style="width: 30%;")


def Packs():
    return Div(id="wordpacks")(
        Ol(*[Li(WordPackRef(wp)) for wp in wordpack_manager.get_all()])
    )

def WordPackEditor(wp: WordPack = None):
    return Div(id="editor")(
        P(f"Editing {wp.name}" if wp else "New word pack"),
        Form(hx_post=save.to(), hx_target="#wordpacks")(
            Input(type="hidden", name="id", value=wp.id if wp else ""),
            Input(type="text", name="name", value=wp.name if wp else "", required=True),
            Textarea(wp.words_ if wp else "", type="text", name="words", rows=10),
            Button("Save", type="submit", value="Save", cls="secondary"),
            style="display: flex; flex-direction: column; gap: 10px; align-items: flex-start;",
        ),
    )


def MainBlock():
    return Titled(
        "Word packs",
        Div(style="display: flex; flex-direction: row; padding: 10px; justify-content: space-around;")(
            Div(
                Div(
                    Form(
                        hx_post=upload.to(), hx_target="#wordpacks"
                    )(
                        Input(type="file", name="file", accept="text/plain"),
                        Button(
                            "Upload", type="submit", value="Upload", cls="secondary"
                        ),
                    )
                ),
                Packs(),
            ),
            WordPackEditor(),
        ),
    )


@rt("/upload", methods=["post"])
async def upload(file: UploadFile):
    if not file:
        return
    text = await file.read()
    wordpack_manager.insert(WordPack(name=file.filename.split(".")[0], words_=text.decode("utf-8")))
    return Packs()

@rt
def save(name: str, words: str, id: str = None):
    id = id or random_id()
    wordpack_manager.upsert(WordPack(id=id, name=name, words_=words))
    return Packs()

@rt
def index(): return MainBlock()

@rt
def editor(id: str):
    pack = wordpack_manager.get_by_id(id)
    return WordPackEditor(pack)

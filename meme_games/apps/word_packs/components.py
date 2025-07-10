from meme_games.core import *
from .domain import *
from ..shared import *


logger = logging.getLogger(__name__)

wordpack_manager = DI.get(WordPackManager)

def ListCard(title, *content):
    "A card with list of something."
    return Div(cls = "col-span-2")(
        Card(H3(title), Div("Something", cls='h-64 uk-background-muted'))
    )
    
def SideBar():
    return Form(
        H3("Wordpack options"),
        LabelInput("Search"),
        Div(FormLabel("Upload from text file"),
            UploadZone(DivCentered(Span("Upload Zone"), UkIcon("upload"), cls=''), name='file', accept='text/plain')),
        LabelSelect(map(Option, ['ru', 'en']), label='Language'),
        cls = 'row-span-2 space-y-5'
    )


def WordPackRef(wp: WordPack):
    from .routes import editor
    return Button(wp.name, hx_get=editor.to(id=wp.id), hx_target="#editor", style="width: 30%;", id=wp.id)


def Packs():
    return Div(id="wordpacks")(
        Ol(*[Li(WordPackRef(wp)) for wp in wordpack_manager.get_all()])
    )

def WordPackEditor(wp: WordPack = None, empty: bool = False, **kwargs):
    from .routes import save, delete
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


def Page():
    from .routes import upload, new
    return MainPage(no_image=True)(
        Container(
            Grid(
                SideBar(),
                ListCard("Wordpacks", Packs()),
                ListCard("Editor", WordPackEditor(empty=True)),
                cols=5
            ),
            cls="pt-14"
        )
    )

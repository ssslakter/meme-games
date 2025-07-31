from meme_games.core import *
from .domain import WordPackRepo, UserManager, WordPack
from ..shared import *


logger = logging.getLogger(__name__)

wordpack_manager = DI.get(WordPackRepo)
user_manager = DI.get(UserManager)

def ListCard(title, *content, cls='', **kwargs):
    "A card with list of something."
    return Div(cls = "col-span-2 lg:col-span-3 xl:col-span-2")(
        Card(H3(title), 
             Div(*content, cls=f'lg:min-h-80 uk-background-muted {cls}', **kwargs)))
    
def SideBar():
    from .routes import new_creation, search, upload
    return Div(
        H3("Wordpack options"),
        Form(onsubmit="return false", id='packs_search')(
            LabelInput("Search", placeholder="Filter by name", name='title'),
            LabelCheckboxX("Show only my wordpacks", name="my_only"),
            hx_trigger="change, input changed delay:500ms, keyup[key==='Enter']",
            hx_post=search, hx_target='#packs_list'),
        DividerSplit(), 
        H4("Create custom wordpack"),
        Form(FormLabel("Upload from text file ('\\n' separated list)"),
            UploadZone(DivCentered(Span("Upload Zone"), UkIcon("upload")), 
            name='file', accept='text/plain'),
            hx_trigger='change', hx_swap='none',
            _='on htmx:afterRequest trigger change on #packs_search then get first <[name="file"]/> in me then set its value to ""',
            hx_post=upload),
        Button("Create empty", hx_post=new_creation, hx_swap='none'),
        cls = 'row-span-2 space-y-5 md:border-r-2 pr-4'
    )


def WordPackRef(wp: WordPack):
    from .routes import editor
    return Button(wp.name, hx_get=editor.to(id=wp.id), hx_target="#editor", id=wp.id)

def ActionBtn(icon, **kwargs):
    return Button(UkIcon(icon), **kwargs)


def render_pack(col, wp: WordPack):
    from .routes import delete, editor
    def _Td(*args, cls='', shrink=True, **kwargs): 
        return Td(*args, cls=f'!p-0 md:!p-2 {cls}',shrink=shrink, **kwargs)
    match col:
        case "Name": return _Td(Div(wp.name, data_pack=wp.id, cls='truncate'))
        case "Author": return _Td(Div(wp.author.name if wp.author else 'unknown'))
        case "edit": return _Td(ActionBtn('pencil'), hx_swap='none', hx_post=editor.to(id=wp.id), shrink=True)
        case "delete": 
            return _Td(ActionBtn('trash', hx_post=delete.to(id=wp.id), hx_target='closest tr',
                                 cls=ButtonT.destructive), shrink=True)
        case _: raise ValueError(f"Unknown column: {col}")

def Packs(wordpacks: list[WordPack]):
    cols2w = dict([("Name", 40), ("Author", 30), ("edit",15), ("delete",15)])
    return TableFromDicts(
        header_data=cols2w.keys(),
        body_data=[dict.fromkeys(cols2w.keys(), wp) for wp in wordpacks],
        body_cell_render=render_pack,
        header_cell_render=lambda col: Th('' if col in ["edit", "delete"] else col, cls=f'w-[{cols2w[col]}%]'),
        cls=(TableT.middle, TableT.divider, TableT.hover, TableT.sm, 'table-fixed'),
        id='packs_list'
    )

def WordPackEditor(wp: Optional[WordPack] = None,
                   readonly: bool = False,
                   submit_button = Button("Save", cls=ButtonT.primary),
                   form_kwargs = None,
                   **kwargs):
    from .routes import save
    editor = Div(id="editor", **kwargs)
    if not wp: return editor
    
    head = DivFullySpaced(
        Div(H4("Pack name: ", cls='inline'), Span(wp.name, data_pack=wp.id), cls='w-full truncate'),
        DivRAligned(H4("Words: ", cls='inline'), Span(len(wp.words)-1)))
    
    return editor(head,
        Form(**(form_kwargs or dict(hx_post=save)),
            _='on htmx:afterRequest trigger change on #packs_search' if not readonly else None)(
            Input(type="hidden", name="id", value=wp.id),
            Input(type="text", name="name", value=wp.name, required=True, placeholder="pack name",
            _=f'on input repeat for el in <[data-pack="{wp.id}"]/> set el.innerText to me.value end') if not readonly else None,
            TextArea(wp.words_ , cls='resize-y whitespace-pre', name="words", 
                     placeholder='words', rows=min(max(len(wp.words), 5), 25), readonly=readonly),
            Div(
                submit_button,
                style="display: flex; flex-direction: row; gap: 10px;",
            ),
            style="display: flex; flex-direction: column; gap: 10px; align-items: flex-start;",
        ),
    )
    
def render_pack_select(col, wp: WordPack, route, **kwargs):
    def _Td(*args, cls='',):
        return Td(*args, cls=f'!p-0 md:!p-2 cursor-pointer {cls}', hx_get=route.to(id=wp.id), **kwargs)
    match col:
        case "Name": return _Td(Div(wp.name, data_pack=wp.id, cls='truncate'))
        case "Author": return _Td(Div(wp.author.name if wp.author else 'unknown'))
        case _: raise ValueError(f"Unknown column: {col}")

def PacksSelect(wordpacks: list[WordPack], route_with_id=None, **kwargs):
    from .routes import editor
    route_with_id = route_with_id or editor
    cols2w = dict([("Name", 50), ("Author", 50)])
    return TableFromDicts(
        header_data=cols2w.keys(),
        body_data=[dict.fromkeys(cols2w.keys(), wp) for wp in wordpacks],
        body_cell_render=partial(render_pack_select, route=route_with_id, **kwargs),
        header_cell_render=lambda col: Th(col, cls=f'w-[{cols2w[col]}%]'),
        cls=(TableT.middle, TableT.divider, TableT.hover, TableT.sm, 'table-fixed'),
        id='packs_select'
    )

def Page(wordpack_id: str):
    packs = wordpack_manager.get_all()
    wpack = wordpack_manager.get_by_id(wordpack_id)
    return MainPage(no_image=True)(
        Container(
            Grid(
                SideBar(),
                ListCard("Wordpacks", Packs(packs), cls='max-h-[719px] overflow-y-auto'),
                ListCard("Editor", WordPackEditor(wpack)),
                cols_sm=1,
                cols_md=3,
                cols_lg=4,
                cols_xl=5,
            ),
            cls=('pt-14', ContainerT.xl)
        )
    )

from meme_games.core import *

PANEL_CLS = "border border-gray-400 shadow-lg bg-white/60 dark:border-gray-700 dark:bg-gray-900/60"
HOVER_CLS = "hover:bg-gray-200 dark:hover:bg-gray-700"

def Panel(*c, cls=(), hoverable=False, rounded='lg', **kwargs) -> FT:
    '''Generic panel component. Use for divs with background color.'''
    cls = (PANEL_CLS, stringify(cls), HOVER_CLS if hoverable else '', f'rounded-{rounded}')
    return Div(*c, cls=cls, **kwargs)

def Card(*c, # Components that go in the body (Main content of the card such as a form, and image, a signin form, etc.)
        header:FT|Iterable[FT]=None, # Component(s) that goes in the header (often a `ModalTitle` and a subtitle)
        footer:FT|Iterable[FT]=None,  # Component(s) that goes in the footer (often a `ModalCloseButton`)
        body_cls='space-y-6', # classes for the body
        header_cls=(), # classes for the header
        footer_cls=(), # classes for the footer
        cls=(), #class for outermost component
        **kwargs # additional arguments for the `CardContainer`
        ) -> FT:
    '''Generic card component.'''
    cls = (PANEL_CLS, stringify(cls), 'rounded-lg')
    return mui.Card(*c, header=header, footer=footer, body_cls=body_cls, header_cls=header_cls, footer_cls=footer_cls, cls=cls, **kwargs)


def Background(url: str = None, no_image: bool = False): 
    bg_cls = ''
    # classes = "absolute top-0 left-0 -z-10 h-full w-full bg-black bg-cover bg-center bg-no-repeat blur-[5px] brightness-50"
    if not no_image: bg_cls = f"bg-[url('{url or '/media/background.jpg'}')]"
    return Div(
        Div(cls="absolute inset-0 backdrop-blur-sm dark:bg-black/30"),
        cls=f"fixed inset-0 z-[-1] bg-cover bg-center bg-fixed filter {bg_cls}",
        hx_swap_oob='true'
    )


# def TextArea(*args, cls=(), **kwargs):
#     return mui.TextArea(*args, cls=cls, **kwargs)
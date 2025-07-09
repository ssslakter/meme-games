from meme_games.core import *

PANEL_CLS = "border border-gray-400 rounded-lg shadow-lg bg-white/60 dark:border-gray-700 dark:bg-gray-900/60"
HOVER_CLS = "hover:bg-gray-200 dark:hover:bg-gray-700"

def Panel(*c, cls=(), hoverable=False, **kwargs) -> FT:
    '''Generic panel component. Use for divs with background color.'''
    return Div(*c, cls=(PANEL_CLS, stringify(cls), HOVER_CLS if hoverable else ''), **kwargs)

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
    cls = (PANEL_CLS, stringify(cls))
    return mui.Card(*c, header=header, footer=footer, body_cls=body_cls, header_cls=header_cls, footer_cls=footer_cls, cls=cls, **kwargs)
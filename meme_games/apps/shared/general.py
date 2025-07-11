from meme_games.core import *

PANEL_CLS = "border border-gray-400 bg-white/60 dark:border-gray-700 dark:bg-gray-900/60"

def Panel(*c, cls=(), rounded='lg', **kwargs) -> FT:
    '''Generic panel component. Use for divs with background color.'''
    cls = ('', stringify(cls), f'rounded-{rounded}')
    return Div(*c, cls=cls, **kwargs)

def Background(url: str = None, no_image: bool = False): 
    bg_cls = ''
    # classes = "absolute top-0 left-0 -z-10 h-full w-full bg-black bg-cover bg-center bg-no-repeat blur-[5px] brightness-50"
    if not no_image: bg_cls = f"bg-[url('{url or '/static/images/background.jpg'}')]"
    return Div(
        Div(cls="absolute inset-0 backdrop-blur-sm dark:bg-black/30"),
        cls=f"fixed inset-0 z-[-1] bg-cover bg-center bg-fixed filter {bg_cls}",
        hx_swap_oob='true'
    )

franken_globals = Style(
"""
"""
)

# def TextArea(*args, cls=(), **kwargs):
#     return mui.TextArea(*args, cls=cls, **kwargs)
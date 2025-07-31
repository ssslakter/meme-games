from meme_games.core import *

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
        id='background',
        hx_swap_oob='true'
    )

def ColoredPoints(value: int):
    v_txt = '+' + str(value) if value >0 else value
    return Span(v_txt, cls=f"{'bg-red-100' if value < 0 else 'bg-green-100' if value > 0 else 'bg-gray-200'} px-2 py-0.5 rounded")
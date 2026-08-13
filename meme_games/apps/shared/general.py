from meme_games.core import *


def classes(*parts) -> str:
    '''Flatten class groups into one string.

    `stringify` joins with `str()`, so a nested group comes out as its Python repr:
    passing `cls=('mg-lobby-tools', cls)` on to a helper that stringifies again wrote
    `('mg-lobby-tools justify-between', ())` into the class attribute, and the hook
    every theme targets never existed. Empty groups leave a literal `()` the same way.
    '''
    out = []
    for p in parts:
        if not p: continue
        out.append(classes(*p) if isinstance(p, (list, tuple)) else str(p))
    return ' '.join(x for x in out if x)


def Panel(*c, cls=(), rounded='lg', **kwargs) -> FT:
    '''Generic panel component. Use for divs with background color.'''
    cls = classes('mg-panel', cls, f'rounded-{rounded}')
    return Div(*c, cls=cls, data_ui='panel', **kwargs)


def GameRail(*content, cls=(), data_ui='game-rail', **kwargs):
    return Div(
        *content,
        cls=classes('mg-game-rail flex min-h-[calc(100vh-7rem)] min-w-0 flex-col gap-4', cls),
        data_ui=data_ui,
        **kwargs,
    )


def GameShell(main, tools, cls=(), **kwargs):
    return Div(
        main,
        tools,
        cls=classes('mg-game-shell grid w-full items-start gap-6 xl:grid-cols-[minmax(0,1fr)_23rem]', cls),
        data_ui='game-shell',
        **kwargs,
    )

def Background(no_image: bool = False):
    bg_cls = '' if no_image else "bg-[url('/static/images/background.jpg')]"
    return Div(
        Div(cls="absolute inset-0 backdrop-blur-sm dark:bg-black/30"),
        cls=f"mg-background fixed inset-0 z-[-1] bg-cover bg-center bg-fixed filter {bg_cls}",
        data_ui='background',
        id='background',
        hx_swap_oob='true'
    )

def ColoredPoints(value: int):
    v_txt = '+' + str(value) if value >0 else value
    sign = 'positive' if value > 0 else 'negative' if value < 0 else 'neutral'
    return Span(v_txt, data_ui='score-change', data_sign=sign, cls=f"""mg-score {'bg-red-100 dark:bg-red-500' if value < 0
                                else 'bg-green-100 dark:bg-green-500' if value > 0 
                                else 'bg-gray-200 dark:bg-gray-700'} px-2 py-0.5 rounded""")

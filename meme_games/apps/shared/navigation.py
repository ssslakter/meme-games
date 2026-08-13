from meme_games.core import *
from .utils import *
from .general import *

def _ThemeButton(icon: str, text: str, action: str, cls: str = ""):
    return Button(
        UkIcon(icon, cls="mr-2", width=20, height=20), text, _=action, cls=(ButtonT.default, cls)
    )


def ThemeSwitcher():
    light_btn = _ThemeButton(
        "sun",
        "Light",
        "on click remove .dark from <html/> then call setThemeMode(false) then call me.blur()",
        "rounded-r-none",
    )
    dark_btn = _ThemeButton(
        "moon",
        "Dark",
        "on click add .dark to <html/> then call setThemeMode(true) then call me.blur()",
        "rounded-l-none",
    )
    return Div(light_btn, dark_btn, cls='mg-theme-switcher', data_ui='theme-switcher')


def Navbar(*args, **kwargs):
    inner_navbar = NavBar(
        Button("Select game", cls=(ButtonT.primary, 'shrink-0 whitespace-nowrap')),
        DropDownNavContainer(
            *[
                Li(A(name, href=page_url(url), _="on click call hideDropdowns()"))
                for name, url in PAGES_REGISTRY.items()
            ]
        )(cls="min-w-48"),
        *args,
        A(UkIcon('user', cls='mr-2', width=20, height=20), 'Settings', href='/me',
          cls=('uk-btn', ButtonT.default, 'inline-flex shrink-0 items-center whitespace-nowrap'),
          hx_boost='false'),
        ThemeSwitcher(),
        brand=A(H3("Meme Games"), href='/', hx_boost='false'),
        cls='mg-navbar-content',
        right_cls='items-center gap-2',
        **kwargs,
    )

    handle = Div(
        Div(cls="w-20 h-1 bg-gray-400 rounded-full"),
        cls="h-4 w-full flex justify-center items-center cursor-pointer",
    )

    return Div(
        inner_navbar,
        handle,
        cls=(
            'mg-navbar uk-card rounded-t-none',
            "fixed top-0 left-0 right-0 z-50",
            "transition-transform duration-300 ease-in-out",
            "transform -translate-y-[calc(100%-1rem)] hover:-translate-y-0 focus-within:-translate-y-0",
        ), data_ui='navbar',
    )


def LobbyPage(*args, navbar_args=(), title: str = '',
              background_url: str = None, no_image: bool = False, cls='pt-4', page='lobby', **kwargs):
    """
    Main page of the app, contains the navbar and the main content.
    """
    return (
        Title(title),
        Div(
        Navbar(*navbar_args),
        Background(background_url, no_image),
        Div(*args, cls=stringify(('mg-page-content', cls)), data_ui='page-content', **kwargs),
        cls="mg-page relative isolate min-h-screen", data_page=page, data_ui='page',
    ))

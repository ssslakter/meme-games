from meme_games.core import *
from .utils import *
from .general import *

def _ThemeButton(icon: str, text: str, action: str, cls: str = ""):
    return Button(
        UkIcon(icon, cls="mr-2", width=20, height=20), text, _=action,
        cls=(ButtonT.default, 'px-4 py-2', cls)
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
        Button("Select game", cls=(ButtonT.primary, 'shrink-0 whitespace-nowrap px-5 py-2')),
        DropDownNavContainer(
            *[
                Li(A(name, href=page_url(url), _="on click call hideDropdowns()"))
                for name, url in PAGES_REGISTRY.items()
            ]
        )(cls="min-w-48"),
        *args,
        A(UkIcon('user', cls='mr-2', width=20, height=20), 'Settings', href='/me',
          cls=('uk-btn', ButtonT.default, 'inline-flex shrink-0 items-center whitespace-nowrap px-4 py-2'),
          hx_boost='false'),
        ThemeSwitcher(),
        brand=A(H3("Meme Games"), href='/', hx_boost='false'),
        cls='mg-navbar-content px-4 py-2 sm:px-6',
        right_cls='items-center gap-3',
        **kwargs,
    )

    return Div(
        inner_navbar,
        cls=(
            'mg-navbar uk-card rounded-t-none',
            "fixed top-0 left-0 right-0 z-50",
        ), data_ui='navbar',
    )


def NicknamePrompt():
    '''Asked once, the first time someone lands on a game without a name of their own.'''
    from meme_games.apps.user.routes import edit_name
    return Modal(
        P('Everyone in the lobby sees this. You can change it later in Settings.', cls=TextT.muted),
        Form(
            Input(name='name', required=True, autofocus=True, maxlength=32,
                  placeholder='e.g. Kate', cls='w-full'),
            Button('Start playing', cls=(ButtonT.primary, 'w-full'), type='submit'),
            hx_put=edit_name, hx_swap='none',
            _="on htmx:afterRequest if event.detail.successful call UIkit.modal('#nickname-prompt').hide()",
            cls='space-y-3'),
        header=ModalTitle('What should we call you?'),
        id='nickname-prompt',
        data_ui='nickname-prompt',
        _="init wait 20ms then call UIkit.modal(me).show()\non hidden remove me",
    )


def LobbyPage(*args, navbar_args=(), title: str = '', user=None,
              no_image: bool = False, cls='', page='lobby', **kwargs):
    """
    Main page of the app, contains the navbar and the main content.
    """
    return (
        Title(title),
        Div(
            Navbar(*navbar_args),
            Background(no_image=no_image),
            Div(*args, cls=stringify(('mg-page-content px-4 py-6 sm:px-6 lg:px-8', cls)),
                data_ui='page-content', **kwargs),
            cls="mg-page relative isolate min-h-screen pt-16", data_page=page, data_ui='page',
        ),
        # outside .mg-page: its stacking context would trap the modal under the navbar
        NicknamePrompt() if user is not None and user.needs_name else None,
    )

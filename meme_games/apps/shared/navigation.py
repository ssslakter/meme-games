from meme_games.core import *
from .settings import *
from .general import *

# will contain name and url for each page
PAGES_REGISTRY = {}


def register_page(name: str, url: str):
    PAGES_REGISTRY[name] = url


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
    return Div(light_btn, dark_btn)


def Navbar(*args, **kwargs):
    inner_navbar = NavBar(
        *args,
        Button("Select game", cls=ButtonT.primary),
        DropDownNavContainer(
            *[
                Li(A(name, href=url, _="on click call hideDropdowns()"))
                for name, url in PAGES_REGISTRY.items()
            ]
        )(cls="min-w-48"),
        ThemeSwitcher(),
        brand=H3("Meme Games"),
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
            'uk-card rounded-t-none',
            "fixed top-0 left-0 right-0 z-50",
            "transition-transform duration-300 ease-in-out",
            "transform -translate-y-[calc(100%-1rem)] hover:-translate-y-0 focus-within:-translate-y-0",
        ),
    )


def MainPage(*args, navbar_args=(), background_url: str = None, no_image: bool = False, **kwargs):
    """
    Main page of the app, contains the navbar and the main content.
    """
    return Div(
        Navbar(*navbar_args),
        Background(background_url, no_image),
        Div(*args, **kwargs),
        cls="relative isolate min-h-screen",
    )

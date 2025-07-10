from meme_games.core import *
from ..shared.settings import *

# will contain name and url for each page
PAGES_REGISTRY = {}


def register_page(name: str, url: str):
    PAGES_REGISTRY[name] = url
    
def _ThemeButton(icon: str, text: str, action: str, extra_cls: str = ''):
    return Div(
        UkIcon(icon, cls="w-5 h-5 mr-2"),
        text,
        _=action,
        cls=f"uk-btn uk-btn-default cursor-pointer {extra_cls}"
    ) 

    
def ThemeSwitcher():
    light_btn = _ThemeButton(
        'sun', 'Light', 
        "on click remove .dark from <html/> then call setThemeMode(false)",
        "rounded-l-md"
    )
    dark_btn = _ThemeButton(
        'moon', 'Dark',
        "on click add .dark to <html/> then call setThemeMode(true)",
        "-ml-px rounded-r-md"
    )
    return Div(light_btn, dark_btn, cls="ml-auto isolate inline-flex rounded-md shadow-sm")



def Navbar():
    inner_navbar = NavBar(
            Button("Select game", cls=(ButtonT.default, "rounded-md")),
            DropDownNavContainer(
                *[Li(A(name, href=url)) for name, url in PAGES_REGISTRY.items()]
            )(cls="min-w-48"),
            ThemeSwitcher(),
        brand=H3("Meme Games"),
    )

    handle = Div(
        Div(cls="w-20 h-1 bg-gray-400 rounded-full"),
        cls="h-4 w-full flex justify-center items-start cursor-pointer",
    )

    container = Div(
        inner_navbar,
        handle,
        cls="bg-base-100/80 backdrop-blur-sm shadow-lg rounded-b-xl"
    )

    return Div(
        container,
        cls=(
            "fixed top-0 left-0 right-0 z-50",
            "transition-transform duration-300 ease-in-out",
            "transform -translate-y-[calc(100%-1rem)] hover:-translate-y-0 focus-within:-translate-y-0"
        )
    )


def MainPage(*args, background_url: str = None, **kwargs):
    """
    Main page of the app, contains the navbar and the main content.
    """
    return Div(
        Navbar(),
        Background(background_url),
        Div(*args, **kwargs),
    cls="relative isolate min-h-screen")

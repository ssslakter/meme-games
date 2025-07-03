from meme_games.core import *

# will contain name and url for each page
PAGES_REGISTRY = {}


def register_page(name: str, url: str):
    PAGES_REGISTRY[name] = url


def Navbar():
    inner_navbar = NavBar(
        Div()(
            Button("Select game"),
            DropDownNavContainer(
                *[Li(A(name, href=url)) for name, url in PAGES_REGISTRY.items()],
                uk_dropdown="delay-hide: 100"
            )(cls="min-w-48"),
        ),
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


def MainPage(*args, **kwargs):
    """
    Main page of the app, contains the navbar and the main content.
    """
    return Div(Navbar(), *args, **kwargs)

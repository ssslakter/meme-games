from meme_games.core import *

# will contain name and url for each page
PAGES_REGISTRY = {
}

def register_page(name: str, url: str):
    PAGES_REGISTRY[name] = url

def Navbar():
    return NavBar(*[H4(A(name,href=url)) for name, url in PAGES_REGISTRY.items()],
                  brand=H3('Meme Games'))

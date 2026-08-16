from meme_games.core import *
from meme_games.domain import *
from ..shared.utils import *
from ..shared.navigation import *
from ..shared import settings_rt as rt


logger = logging.getLogger(__name__)

GAME_BLURBS = {
    "Alias": "Guess the words before time runs out!",
    "Codenames": "Give clever clues to find your team's words.",
    "Who Am I": "Ask yes/no questions to guess your identity.",
    "Videos 🚧": "Sync videos and enjoy them with friends.",
}


def GameCard(title, desc, href):
    return A(
        H2(title, cls="text-xl font-semibold mb-2 text-gray-900 dark:text-[color:var(--card-foreground)]"),
        P(desc, cls="text-sm text-gray-600 dark:text-[color:var(--muted-foreground)]"),
        href=href,
        cls=(
            "mg-game-card mg-game-link p-6 rounded-xl shadow hover:shadow-lg transition "
            "bg-white dark:bg-[color:var(--card)] "
            "border border-gray-200 dark:border-[color:var(--border)]"
        ), data_ui='game-card'
    )



@rt
def index():
    footer = Footer(Div(
                P("© 2025 Meme games. All rights reserved.",
                  cls="text-gray-600 dark:text-[color:var(--muted-foreground)]"),
                Div(
                    DivHStacked(
                        UkIcon("github"),
                        A("Repo",href="https://github.com/ssslakter/meme-games", cls="hover:underline",), cls=""),
                    cls="flex space-x-4 mt-4 sm:mt-0 text-gray-600 dark:text-[color:var(--muted-foreground)]"
                ),
                cls="max-w-5xl mx-auto px-4 py-8 flex flex-col sm:flex-row justify-between items-center text-sm"
            ),
             cls="bg-gray-100 dark:bg-[color:var(--secondary)] border-t border-gray-200 dark:border-[color:var(--border)] mt-12"
        )
    return (Title("Home"),
            Div(
        Main(
            Navbar(),
            Section(
                H1(
                    "Welcome to Meme games",
                    cls="text-4xl font-bold mb-6 text-center text-gray-900 dark:text-[color:var(--foreground)]"
                ),
                P(
                    "Play fun party games with friends or enjoy streaming together — all in one place.",
                    cls="text-lg mb-12 text-center text-gray-700 dark:text-[color:var(--muted-foreground)]"
                ),
                Div(
                    *[GameCard(name, desc, page_url(PAGES_REGISTRY[name]))
                      for name, desc in GAME_BLURBS.items() if name in PAGES_REGISTRY],
                    cls="mg-game-cards grid gap-6 sm:grid-cols-2 lg:grid-cols-4"
                ),
                cls=(
                    "max-w-5xl mx-auto px-4 py-12 "
                    "bg-gray-50 dark:bg-[color:var(--background)]"
                )
            ),
            # Section(
            #     H2(
            #         "Ready to Play?",
            #         cls="text-2xl font-bold mb-4 text-gray-900 dark:text-gray-100"
            #     ),
            #     P(
            #         "Create a lobby, invite your friends, and start having fun in seconds.",
            #         cls="mb-6 text-gray-700 dark:text-gray-300"
            #     ),
            #     A(
            #         "Create Lobby",
            #         href="/create-lobby",
            #         cls="inline-block px-6 py-3 bg-blue-600 text-white rounded-lg shadow hover:bg-blue-700 transition"
            #     ),
            #     cls="bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 py-8 mt-12 text-center"
            # ),
            cls="mg-page-content flex-1", data_ui='page-content'
        ),
        footer,
        cls="mg-page flex flex-col min-h-screen pt-20 bg-gray-50 dark:bg-[color:var(--background)]",
        data_page='home', data_ui='page'
    ))

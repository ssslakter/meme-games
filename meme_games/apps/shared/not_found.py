from meme_games.core import *
from .navigation import *

static_dir = Path(__file__).parent.parent / "static"

# TODO make adaptive canvas for different screen sizes
def not_found(req: Request, exc):
    if req.method.lower() != "get":
        return Response("Not found", status_code=404)
    model_path = "/media/shizuku/shizuku.model.json"
    return (
        Title("Not Found"),
        MainPage(
            H1("404😭! Sorry, this page does not exist.", cls="mt-12 text-center"),
            Div(cls="flex-1"),  # Spacer
            Div(
                Canvas(
                    id="canvas",
                    cls="aspect-1 max-h-[80vh] max-w-full mx-auto brightness-75",
                    style="opacity: 0;",
                    _=f"""init call initLive2D(me, "{model_path}")
                                then wait 10ms then transition my opacity to 1 over 4000ms end""",
                ),
                cls="flex justify-center",
            ),
            hx_boost="true",
            cls="flex flex-col items-center h-screen",
        ),
    )

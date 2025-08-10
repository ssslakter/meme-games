from ..shared.utils import register_route
from meme_games.apps.shared import register_page
from meme_games.core import *
from ..shared import *
from .components import *

rt = APIRouter('/video')
register_route(rt)
register_page("Videos", rt.prefix)

logger = logging.getLogger(__name__)


@rt
def index():
    return MainPage(H1("Video"),
                  Div(hx_ext='ws', ws_connect=ws_url,
                      hx_on__ws_after_message = 'getViewerData(event)',
                      hx_on__ws_open='window.ws = event.detail.socketWrapper'),
                  ViewerBlock(),
                  no_image=True)


@rt
def stream():
    return MainPage(
        H1("Streamer page"),
        Div(hx_ext='ws', ws_connect=ws_url,
            hx_on__ws_after_message = 'getWsEvent(event)',
            hx_on__ws_open='window.ws = event.detail.socketWrapper'),
        StreamerBlock(),
        no_image=True)


users: Dict[str, WebSocket] = {}
def on_conn(ws, send): users[str(id(ws))] = ws
def on_disconn(ws): users.pop(str(id(ws)), None)

@ws_rt.ws('/video', conn=on_conn, disconn=on_disconn)
async def ws(ws, sess, data):
    for u in users.values():
        if u!= ws:
            await u.send_json(data)

ws_url = ws_rt.wss[-1][1]
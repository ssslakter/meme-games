import logging
from meme_games.init import *
from . import rt

logger = logging.getLogger(__name__)

ar = APIRouter(prefix='/video')


def YoutubePlayer(video_id: str):
    return (Iframe(id='player', src=f'https://www.youtube.com/embed/{video_id}?enablejsapi=1&origin=http://localhost:8000',
                   frameborder=0, style='border: solid 4px #37574F', _='on onStateChange log event'),
            Script(f'on load set global player to createYTplayer("{video_id}", "player") then log player', type='text/hyperscript')
            )


@ar
def index():
    return Titled("Video",
                  Form(
                      Input(type='text', name='id', placeholder="Enter video ID"),
                      Button("Load", type='submit'),
                      hx_get='/video/yt', hx_target='#player-block', hx_swap='innerHTML', hx_include='this'),
                  Div(id='player-block'),
                  Div(hx_ext='ws', ws_connect='/video/ws'))


@ar('/yt')
def get(id: str):
    return YoutubePlayer(id)


@ar.ws('/ws')
async def ws(sess, data):
    print(data)

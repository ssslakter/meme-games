from meme_games.core import *
from .controls import *

def StreamerBlock():
    from ..routes import ws_url
    ws = Div(hx_ext='ws', ws_connect=ws_url,
            hx_on__ws_before_message = 'handleMessage(event)',
            hx_on__ws_open='ws = event.detail.socketWrapper; makeCall()'),
    
    return DivVStacked(
        ws, 
        Video(id='video', width=800, autoplay=True, muted=True, playsinline=True, controls=True),
        cls="border",
    )

def StreamingMain(is_muted=True, is_sharing=False, is_video_on=False):
    return DivCentered(
        StreamerBlock(),
        StreamingControls(is_muted, is_sharing, is_video_on)
    )

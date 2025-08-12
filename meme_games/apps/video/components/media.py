from meme_games.core import *
from .controls import *

def StreamerBlock():
    from ..routes import ws_url
    vid, btn = 'video', 'button'
    ws = Div(hx_ext='ws', ws_connect=ws_url,
            hx_on__ws_before_message = 'handleMessage(event)',
            hx_on__ws_open='ws = event.detail.socketWrapper'),
    
    return DivVStacked(
        ws, 
        Video(id=vid, width=800, autoplay=True, muted=True, playsinline=True, controls=True,
              _='on "start-stream" from body set me.srcObject to event.detail'),
        cls="border",
    )

def StreamingMain(is_muted=False, is_sharing=False, is_video_on=True):
    return DivCentered(
        StreamerBlock(),
        StreamingControls(is_muted, is_sharing, is_video_on),
    )

from meme_games.core import *

# Helper to make a round control button with icon + toggle support
def ControlButton(icon_on: str, icon_off: str, active: bool, title_on: str, title_off: str, **kwargs):
    return Div(Button(
        UkIcon(icon_on if active else icon_off),
        cls='absolute inset-0  w-full h-full' + (ButtonT.ghost if not active else ButtonT.destructive),
        title=title_off if not active else title_on,
        **kwargs),
        cls="flex items-center justify-center rounded-full w-12 h-12 uk-card overflow-hidden")


# Specific control buttons with toggle flag
def MuteButton(is_muted: bool): 
    return ControlButton("mic", "mic-off", not is_muted, "Unmute", "Mute")

def ScreenShareButton(is_sharing: bool): 
    return ControlButton("monitor-x", "monitor-up", 
                         is_sharing, 
                         "Stop Share", "Share Screen",
                         hx_on_click='startStream()')(id='stream-btn', hx_swap_oob='true')

def VideoButton(is_video_on: bool): 
    return ControlButton("video-off", "video", is_video_on, "Turn Off Video", "Turn On Video")


# Controls container
def StreamingControls(is_muted=False, is_sharing=False, is_video_on=True):
    return Div(
        MuteButton(is_muted),
        ScreenShareButton(is_sharing),
        VideoButton(is_video_on),
        cls="fixed bottom-4 left-1/2 -translate-x-1/2 flex gap-4"
    )
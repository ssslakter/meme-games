from meme_games.core import *


def ControlButton(
    icon_on: str, icon_off: str, active: bool, title_on: str, title_off: str, **kwargs
):
    def btn(icon: str, title: str, cls="", **kw):
        return Button(
            UkIcon(icon),
            cls="absolute inset-0  w-full h-full " + cls,
            title=title,
            **{**kwargs, **kw},
        )

    on_cls = ButtonT.destructive
    off_cls = ButtonT.ghost
    extra = " hidden" if not active else ""
    return Div(
        btn(icon_on, title_on, cls=on_cls + extra),
        btn(icon_off, title_off, cls=off_cls + " hidden".removesuffix(extra)),
        cls="flex items-center justify-center rounded-full w-12 h-12 uk-card overflow-hidden",
    )


def MuteButton(is_muted: bool):
    return ControlButton("mic-off", "mic", is_muted, "Unmute", "Mute")(
        id="mic", hx_on_click="toggleMicrophone()"
    )


def ScreenShareButton(is_sharing: bool):
    return ControlButton(
        "monitor-x", "monitor-up", is_sharing, "Stop Share", "Share Screen"
    )(id="screen", hx_on_click="toggleScreenShare()")


def VideoButton(is_video_on: bool):
    return ControlButton(
        "video-off",
        "video",
        is_video_on,
        "Turn Off Video",
        "Turn On Video",
    )(
        id="camera",
        hx_on_click="toggleCamera()",
    )


def StreamingControls(is_muted=True, is_sharing=False, is_video_on=False):
    return Div(
        MuteButton(is_muted),
        ScreenShareButton(is_sharing),
        VideoButton(is_video_on),
        cls="fixed bottom-4 left-1/2 -translate-x-1/2 flex gap-4",
    )

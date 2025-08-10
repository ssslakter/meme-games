from meme_games.core import *

# def YoutubePlayer(video_id: str):
#     return (Iframe(id='player', src=f'https://www.youtube.com/embed/{video_id}?enablejsapi=1&origin=http://localhost:8000',
#                    frameborder=0, style='border: solid 4px #37574F', _='on onStateChange log event'),
#             Script(f'on load set global player to createYTplayer("{video_id}", "player") then log player', type='text/hyperscript')
#             )


def StreamerBlock():
    vid, btn = 'video', 'button'
    return Div(
        Button("Start stream", id=btn),
        Video(id=vid, width=400, autoplay=True, muted=True, playsinline=True),
        Script(f"initStreamer('#{vid}', '#{btn}')")
    )


def ViewerBlock():
    vid = 'video'
    return Div(
        Video(id=vid, width=800, autoplay=True, playsinline=True),
        Script(f"initViewer('#{vid}')")
    )

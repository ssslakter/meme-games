from meme_games.core import *
from fasthtml import svg

def Timer(time: dt.timedelta | float = dt.timedelta(hours=1),
          total: dt.timedelta | float = 60,
          renderer=Span,
          data_render='text', paused=False):
    if isinstance(time, dt.timedelta):
        time = time.total_seconds()
    return Div(
        renderer(data_duration=total* 1000,
                 data_remaining=time * 1000,
                 timer_text=True, timer=None if paused else True,
                 data_render=data_render,
                 _=None if paused else 'init immediately set @data-target to (Date.now()+@data-remaining as Number) as Date'),
        _='init renderTextTimers()', cls='mg-timer', data_ui='timer')

def CircleTimer(time: dt.timedelta | float, **kwargs):
    seconds = time.total_seconds() if isinstance(time, dt.timedelta) else time
    circumference = 2 * math.pi * 45
    renderer = svg.Svg(
            svg.Circle(cx=50, cy=50, r=45, stroke="currentColor", stroke_width=10,
                   fill="none", cls="text-gray-300"),
            svg.Circle(cx=50, cy=50, r=45, stroke="currentColor", stroke_width=10,
                   fill="none", cls="text-green-500",
                   ring_fg=True, #used in timer.js
                   stroke_dasharray=f"{circumference:.3f}",
                   stroke_dashoffset=f"{circumference:.3f}"),
            svg.Text(f'{max(0, math.ceil(seconds))}s', x="50%", y="50%", text_anchor="middle", timer_text=True,
                  dominant_baseline="middle", cls="fill-current"),
            viewBox="0 0 100 100", cls="w-20 h-20")
    return Timer(time, renderer=renderer, data_render='circle', **kwargs)

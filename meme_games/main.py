
from .init import *
from .common.components import rt as common_rt
from .whoami.components import rt as whoami_rt
from .video.components import rt as video_rt
from .codenames.components import rt as codenames_rt
from .word_packs.components import rt as word_packs_rt

common_rt.to_app(app)
whoami_rt.to_app(app)
video_rt.to_app(app)
word_packs_rt.to_app(app)
codenames_rt.to_app(app)

serve(port=8000)

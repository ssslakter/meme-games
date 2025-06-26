
from .init import *
from .common import rt as common_rt
from .whoami import rt as whoami_rt
from .video import *
from .codenames import rt as codenames_rt
from .word_packs import rt as word_packs_rt

common_rt.to_app(app)
whoami_rt.to_app(app)
word_packs_rt.to_app(app)
codenames_rt.to_app(app)

serve(port=8000)

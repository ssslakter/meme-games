import logging
from meme_games.common.components import *
from .domain import *
from . import rt

logger = logging.getLogger(__name__)


@rt.get('/debug/test')
def get():
    return Titled(
        'test'
    )
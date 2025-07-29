from meme_games.core import *
from .utils import register_route

ws_rt = APIRouter('/ws')
register_route(ws_rt)

from meme_games.core import *


rt = APIRouter('/word_packs')

logger = logging.getLogger(__name__)


@rt.get('/debug/test')
def get():
    return Titled(
        'test'
    )
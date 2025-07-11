from meme_games.core import *
from meme_games.domain import *
from ..shared import *
from .components import *

#---------------------------------#
#------------- Routes ------------#
#---------------------------------#

rt = APIRouter('/me')

logger = logging.getLogger(__name__)

user_manager = DI.get(UserManager)


@rt
def index():
    return MainPage(
        no_image=True,
    )
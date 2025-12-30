from ..shared.utils import register_route, get_common_services
from meme_games.core import *
from meme_games.domain import *
from ..shared import *
from .components import *

#---------------------------------#
#------------- Routes ------------#
#---------------------------------#

rt = APIRouter('/me')
register_route(rt)

logger = logging.getLogger(__name__)

lobby_service, user_manager = get_common_services()


@rt
def index():
    return LobbyPage(
        no_image=True,
    )


#---------------------------------#
#------------ REST API------------#
#---------------------------------#

rt = APIRouter('/me/api')
register_route(rt)

@rt
def edit_name(req: Request, name: str):
    u: User = req.state.user
    u.name = name
    user_manager.update(u)
    lobby_service.sync_active_lobbies_user(u)
    return asdict(u)
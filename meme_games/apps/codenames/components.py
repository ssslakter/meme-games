from meme_games.core import *
from meme_games.domain import *
from .domain import *
from ..shared.components import *

rt = APIRouter('/codenames')

logger = logging.getLogger(__name__)


lobby_service = DI.get(LobbyService)
user_manager = DI.get(UserManager)

def MainBlock(reciever: CodenamesPlayer | User, lobby: Lobby):
    return Div(
        Div(cls='background'),
        Settings(reciever, lobby),
    )


#---------------------------------#
#------------- Routes ------------#
#---------------------------------#


@rt('/{lobby_id}', methods=['get'])
def lobby(req: Request, lobby_id: str = None):
    if not lobby_id: return Redirect(req.url_for('lobby', lobby_id=random_id()))
    u: User = req.state.user
    lobby, was_created = lobby_service.get_or_create(u, lobby_id, CodenamesPlayer)
    if was_created: lobby_service.update(lobby)
    m = lobby.get_member(u.uid)
    req.session['lobby_id'] = lobby.id
    req.bodykw['cls'] = 'codenames'
    return (Title(f'Codenames lobby: {lobby.id}'),
            MainBlock(m or u, lobby))
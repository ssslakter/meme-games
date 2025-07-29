from ..shared.utils import register_route
from meme_games.core import *
from meme_games.domain import *
from .domain import *
from ..word_packs.domain import *
from ..shared.utils import *
from ..shared.navigation import *
from ..shared.settings import *

rt = APIRouter('/codenames')
register_route(rt)

logger = logging.getLogger(__name__)


lobby_service = DI.get(LobbyService)
wordpack_manager = DI.get(WordPackRepo)
user_manager = DI.get(UserManager)


def WordpackSelector(r: CodenamesPlayer | User):
    return Div(
        H3('Wordpack selector'),
        Select(hx_post=select_pack, hx_trigger='change', hx_target='#game', name='wordpack')(
        *[Option(wp.name, value=wp.id) for wp in wordpack_manager.get_all()],
        ) 
    )

def MainBlock(reciever: CodenamesPlayer | User, lobby: Lobby):
    return Div(
        Div(id='game'),
        Settings(reciever, lobby),
        WordpackSelector(reciever),
    )

#---------------------------------#
#------------- Routes ------------#
#---------------------------------#

# @rt
# def index():
#     return Div(
#         H1("Game Lobby"),
#         # ... other components for the lobby (like a player list) ...
#         Div(cls="mt-8 max-w-md")( # Constrain the width for a "small box" feel
#         )
#     )

@rt('/{lobby_id}', methods=['get'])
def index(req: Request, lobby_id: str = None):
    if not lobby_id: return redirect(random_id())
    u: User = req.state.user
    lobby, was_created = lobby_service.get_or_create(u, lobby_id, CodenamesPlayer)
    if was_created: lobby_service.update(lobby)
    m = lobby.get_member(u.uid)
    req.session['lobby_id'] = lobby.id
    req.bodykw['cls'] = 'codenames'
    # TODO: comment when done
    return Redirect('/work-in-progress')
    return Title(f"Codenames lobby: {lobby.id}"), MainBlock(m or u, lobby)

def redirect(lobby_id: str): return Redirect(index.to(lobby_id=lobby_id))


@rt
def select_pack(wordpack: str):
    return Div(
        *[WordCard(word, CardColor.NEUTRAL) for word in wordpack_manager.get_by_id(wordpack).words],
    )

register_page('Code Names', '/codenames')
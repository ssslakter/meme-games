from ..shared.utils import register_route
from ..shared.navigation import LobbyPage, ThemeSwitcher
from meme_games.core import *
from meme_games.domain import *
from .components import *

#---------------------------------#
#------------- Routes ------------#
#---------------------------------#

rt = APIRouter('/me')
register_route(rt)

logger = logging.getLogger(__name__)

user_manager = DI.get(UserManager)


@rt
def index(req: Request):
    return LobbyPage(
        Container(
            H1('User settings'),
            IdentitySettings(req.state.user),
            Card(H3('Color mode'), ThemeSwitcher(), cls='mg-settings-section', data_ui='theme-settings'),
            CustomCssSettings(),
            cls='max-w-4xl pt-24 pb-12 space-y-6'),
        title='User settings',
        no_image=True,
        page='settings',
    )


@rt('/name', methods=['put'])
async def edit_name(req: Request, name: str):
    u: User = req.state.user
    name = ' '.join(name.split())
    if not name: raise HTTPException(400, 'Nickname cannot be empty')
    u.name = name
    user_manager.update(u)
    lobby_service = DI.get(LobbyService)
    lobby_service.sync_active_lobbies_user(u)
    if lobby := lobby_service.get_lobby(req.session.get('lobby_id')):
        await notify_all(lobby, lambda r, *_: UserName(r, u))
    return IdentitySettings(u)


async def modify_avatar(req: Request, file: Optional[UploadFile] = None):
    u: User = req.state.user
    if file: await u.set_picture(file)
    else: u.reset_picture()
    user_manager.update(u)
    lobby_service = DI.get(LobbyService)
    lobby_service.sync_active_lobbies_user(u)
    if lobby := lobby_service.get_lobby(req.session.get('lobby_id')):
        def update(*_):
            return (Avatar(u)(hx_swap_oob=f"outerHTML:[data-avatar='{u.uid}']"),
                    AvatarBig(u)(hx_swap_oob=f"outerHTML:[data-avatar-big='{u.uid}']"))
        await notify_all(lobby, update)
    return IdentitySettings(u)


@rt('/avatar', methods=['post'])
async def edit_avatar(req: Request, file: UploadFile):
    return await modify_avatar(req, file)


@rt('/avatar', methods=['delete'])
async def reset_avatar(req: Request):
    return await modify_avatar(req)

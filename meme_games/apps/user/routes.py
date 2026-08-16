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
            SettingsSaveBar(),
            cls='max-w-4xl py-12 space-y-6'),
        title='User settings',
        no_image=True,
        page='settings',
    )


async def sync_user(req: Request, u: User, avatar: bool = False) -> None:
    user_manager.update(u)
    lobby_service = DI.get(LobbyService)
    lobby_service.sync_active_lobbies_user(u)
    if lobby := lobby_service.get_lobby(req.session.get('lobby_id')):
        def update(r, *_):
            avatars = (Avatar(u)(hx_swap_oob=f"outerHTML:[data-avatar='{u.uid}']"),
                       AvatarBig(u)(hx_swap_oob=f"outerHTML:[data-avatar-big='{u.uid}']")) if avatar else ()
            return (UserName(r, u), *avatars)
        await notify_all(lobby, update)


@rt('/profile', methods=['post'])
async def save_profile(req: Request, name: str, file: Optional[UploadFile] = None):
    u: User = req.state.user
    name = ' '.join(name.split())
    if not name: raise HTTPException(400, 'Nickname cannot be empty')
    u.name, u.named = name, True
    picked = bool(file and getattr(file, 'filename', ''))
    if picked: await u.set_picture(file)
    await sync_user(req, u, avatar=picked)
    return IdentitySettings(u)


@rt('/name', methods=['put'])
async def edit_name(req: Request, name: str):
    return await save_profile(req, name)


@rt('/avatar', methods=['delete'])
async def reset_avatar(req: Request):
    u: User = req.state.user
    u.reset_picture()
    await sync_user(req, u, avatar=True)
    return IdentitySettings(u)

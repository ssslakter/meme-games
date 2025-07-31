from meme_games.core import *
from meme_games.domain import *

def UserRemover(uid: str):
    data_classes = ['user', 'username', 'avatar', 'avatar-big', 'notes']
    return tuple(Div(hx_swap_oob=f"delete:[data-{cls}='{uid}']") for cls in data_classes)

def get_avatar_path(u: User):
    filename = u.avatar
    filename = ('/user-content/' + filename) if filename else '/static/images/default-avatar.jpg'
    return filename

def UserName(r: User, u: User, is_connected=True):
    """Renders the user's name as a styled HTML span."""
    return Span(B(u.name) if r==u else u.name, data_username = u.uid,
                    hx_swap_oob=f"outerHTML:span[data-username='{u.uid}']",
                    cls=' opacity-50' if not is_connected else '')

def MemberName(r: User, m: LobbyMember, **kwargs):
    return UserName(r, m.user, is_connected=m.is_connected, **kwargs)


def UserInfo(r: User, user: User, is_connected=True, cls='', **kwargs):
    return DivLAligned(
            Span(cls=f"relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full bg-secondary")(Avatar(user)),
            Span(UserName(r, user, is_connected), cls=f'{TextT.sm} {TextT.medium} {cls}', **kwargs))


def Avatar(u: User):
    return Img(cls=f"aspect-square h-10 w-10", alt="Avatar", loading="lazy", src=get_avatar_path(u), data_avatar=u.uid)
    

def AvatarBig(u: User):
    return Div(style=f'background-image: url({get_avatar_path(u)})', cls="w-full h-full bg-cover bg-center bg-no-repeat dark:brightness-75", data_avatar_big=u.uid)

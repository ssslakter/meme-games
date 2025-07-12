from meme_games.core import *
from meme_games.domain import *


def get_avatar_path(u: User):
    filename = u.avatar
    filename = ('/user-content/' + filename) if filename else '/static/images/default-avatar.jpg'
    return filename

def UserName(r: User, u: User, is_connected=True, cls='username', **kwargs):
    """Renders the user's name as a styled HTML span."""
    cls += ' opacity-50' if not is_connected else ''
    return Span(B(u.name) if r==u else u.name, data_username = u.uid, cls=cls, **kwargs)


def UserInfo(r: User, user: User, **kwargs):
    return DivLAligned(
            Span(cls=f"relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full bg-secondary")(Avatar(user)),
            P(UserName(r, user, **kwargs), cls=(TextT.sm, TextT.medium))
            )

def Avatar(u: User):
    return Img(cls=f"aspect-square h-10 w-10", alt="Avatar", loading="lazy", src=get_avatar_path(u), data_avatar=u.uid)
    

def AvatarBig(u: User):
    return Div(style=f'background-image: url({get_avatar_path(u)})', cls="w-full h-full bg-cover bg-center bg-no-repeat dark:brightness-75", data_avatar_big=u.uid)

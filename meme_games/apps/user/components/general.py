from meme_games.core import *
from meme_games.domain import *

def UserRemover(uid: str):
    data_classes = ['user', 'username', 'avatar', 'avatar-big', 'notes']
    return tuple(Div(hx_swap_oob=f"delete:[data-{cls}='{uid}']") for cls in data_classes)

def get_avatar_path(u: User):
    filename = u.avatar
    filename = ('/user-content/' + filename) if filename else '/static/images/default-avatar.jpg'
    return filename

def UserName(r: User, u: User, is_connected=True, cls='', **kwargs):
    """Renders the user's name as a styled HTML span."""
    return Span(B(u.name) if r==u else u.name, data_username = u.uid,
                    hx_swap_oob=f"outerHTML:span[data-username='{u.uid}']",
                    data_ui='user-name',
                    cls=stringify((cls, 'opacity-50' if not is_connected else '')),
                    **kwargs)

def MemberName(r: User, m: LobbyMember, **kwargs):
    return UserName(r, m.user, is_connected=m.is_connected, **kwargs)


def UserInfo(r: User, user: User, is_connected=True, cls='', **kwargs):
    return DivLAligned(
            Span(cls="relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full bg-secondary")(Avatar(user)),
            Span(UserName(r, user, is_connected), cls=f'{TextT.sm} {TextT.medium} {cls}', **kwargs),
            cls='mg-user', data_ui='user')


def Avatar(u: User, cls="aspect-square h-10 w-10", **kwargs):
    return Img(cls=stringify(('mg-avatar', cls)), alt="Avatar", loading="lazy",
               src=get_avatar_path(u), data_avatar=u.uid, data_ui='avatar', **kwargs)
    

def AvatarBig(u: User, cls="w-full h-full bg-cover bg-center bg-no-repeat dark:brightness-75", **kwargs):
    return Div(style=f'background-image: url({get_avatar_path(u)})',
               cls=stringify(('mg-avatar-big', cls)), data_avatar_big=u.uid,
               data_ui='avatar-big', **kwargs)


def IdentitySettings(u: User):
    from ..routes import edit_avatar, edit_name, reset_avatar

    return Card(
        H3('Profile'),
        Div(
            Div(
                Avatar(u, cls='h-28 w-28 rounded-full object-cover'),
                Button('Remove avatar', cls=(ButtonT.destructive, 'whitespace-nowrap'), hx_delete=reset_avatar,
                       hx_confirm='Remove your avatar?', hx_target='#identity-settings', hx_swap='outerHTML'),
                cls='w-48 shrink-0 flex flex-col items-center gap-3'),
            Div(
                Form(
                    LabelInput('Nickname', name='name', value=u.name, required=True, cls='flex-1'),
                    Button('Save', cls=(ButtonT.primary, 'w-28 shrink-0'), type='submit'),
                    hx_put=edit_name, hx_target='#identity-settings', hx_swap='outerHTML',
                    cls='flex flex-col sm:flex-row sm:items-end gap-3'),
                Form(
                    FormLabel('Avatar'),
                    Div(
                        Upload('Choose image', name='file', accept='image/*',
                               cls='min-w-0 flex-1', button_cls=(ButtonT.default, 'w-full justify-start')),
                        Button('Upload', cls=(ButtonT.primary, 'w-28 shrink-0'), type='submit'),
                        cls='flex flex-col sm:flex-row sm:items-center gap-3'),
                    hx_post=edit_avatar, hx_target='#identity-settings', hx_swap='outerHTML',
                    cls='space-y-2'),
                cls='min-w-0 flex-1 space-y-5'),
            cls='flex flex-col sm:flex-row gap-6 items-start'),
        id='identity-settings', cls='mg-settings-section', data_ui='identity-settings')


def CustomCssSettings():
    return Card(
        H3('Custom CSS'),
        P('Stored only in this browser. This page never applies custom CSS, so you can always return here to disable it.',
          cls=TextT.muted),
        Form(
            Div(
                CheckboxX(id='custom-css-enabled', cls='shrink-0'),
                FormLabel('Enable custom CSS', fr='custom-css-enabled', cls='m-0 cursor-pointer'),
                cls='flex items-center gap-2'),
            TextArea(id='custom-css-editor', rows=20, spellcheck='false',
                     placeholder='html:not(.dark) {\n  /* light theme */\n}\n\nhtml.dark {\n  /* dark theme */\n}',
                     cls='w-full resize-y font-mono whitespace-pre'),
            P(id='custom-css-error', cls='text-destructive', role='alert'),
            P(id='custom-css-status', cls=TextT.muted, role='status'),
            Div(
                Button('Save CSS', cls=ButtonT.primary, type='submit'),
                Button('Clear CSS', type='button', onclick='clearCustomCss()'),
                cls='flex flex-wrap gap-2'),
            onsubmit='return saveCustomCss(event)', cls='space-y-4'),
        Details(
            Summary('Selector reference and starter CSS'),
            Pre(Code('''html:not(.dark) { --background: 45 60% 96%; }
html.dark { --background: 260 25% 8%; }

[data-page="alias"] .mg-game-card { border-radius: 1.5rem; }
[data-ui="navbar"] { backdrop-filter: blur(12px); }
[data-ui="player-card"] { box-shadow: 0 0 1rem hotpink; }'''),
                cls='overflow-auto p-3'),
            P('Stable hooks: .mg-page, .mg-page-content, .mg-navbar, .mg-background, .mg-game, .mg-game-card, .mg-user, .mg-avatar, .mg-spectators, .mg-timer, .mg-game-controls, and [data-page].',
              cls=TextT.muted),
            cls='pt-2'),
        cls='mg-settings-section', data_ui='custom-css-settings')

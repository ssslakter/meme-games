from meme_games.core import *
from meme_games.domain import *
import fasthtml.common as fh

def UserRemover(uid: str):
    data_classes = ['user', 'username', 'avatar', 'avatar-big', 'notes']
    return tuple(Div(hx_swap_oob=f"delete:[data-{cls}='{uid}']") for cls in data_classes)

def get_avatar_path(u: User):
    filename = u.avatar
    filename = ('/user-content/' + filename) if filename else '/static/images/default-avatar.jpg'
    return filename

def HostBadge():
    """The lobby host, marked the same way in every game."""
    return Span(UkIcon('crown', width=12, height=12), 'Host',
                cls='mg-host-badge', data_ui='host-badge', title='Lobby host')


def UserName(r: User, u: User, is_connected=True, is_host=False, cls='', **kwargs):
    """Renders the user's name as a styled HTML span."""
    return Span(B(u.name) if r==u else u.name,
                    Span('AI', cls='ml-2 rounded-full border px-1.5 py-0.5 text-[.65rem] font-semibold')
                        if u.kind == 'agent' else None,
                    HostBadge() if is_host else None,
                    data_username = u.uid,
                    hx_swap_oob=f"outerHTML:span[data-username='{u.uid}']",
                    data_ui='user-name',
                    # an agent has no websocket, so `is_connected` is never true for one -
                    # dimming it read as "gone" when it was sitting right there playing
                    cls=stringify((cls, 'opacity-50' if not is_connected and u.kind != 'agent' else '')),
                    **kwargs)

def MemberName(r: User, m: LobbyMember, **kwargs):
    return UserName(r, m.user, is_connected=m.is_connected, is_host=m.is_host, **kwargs)


def UserInfo(r: User, user: User, is_connected=True, is_host=False, cls='', avatar_cls='h-10 w-10', **kwargs):
    return Div(
        Span(Avatar(user, cls=f'aspect-square {avatar_cls}'),
             cls=f'relative flex {avatar_cls} shrink-0 overflow-hidden rounded-full bg-secondary'),
        Span(UserName(r, user, is_connected, is_host), cls=f'min-w-0 truncate {TextT.sm} {TextT.medium} {cls}', **kwargs),
        cls='mg-user flex min-w-0 items-center gap-3', data_ui='user')


def Avatar(u: User, cls="aspect-square h-10 w-10", **kwargs):
    return Img(cls=stringify(('mg-avatar', cls)), alt="Avatar", loading="lazy",
               src=get_avatar_path(u), data_avatar=u.uid, data_ui='avatar', **kwargs)
    

def AvatarBig(u: User, cls="w-full h-full bg-cover bg-center bg-no-repeat dark:brightness-75", **kwargs):
    return Div(style=f'background-image: url({get_avatar_path(u)})',
               cls=stringify(('mg-avatar-big', cls)), data_avatar_big=u.uid,
               data_ui='avatar-big', **kwargs)


AVATAR_PICKED_JS = (
    "const f = this.files[0];"
    "document.getElementById('avatar-file-name').textContent = f ? f.name : 'No file chosen';"
    # inline handlers run inside `with (document)`, where a bare `URL` is the document's own URL string
    "if (f) document.getElementById('avatar-preview').src = window.URL.createObjectURL(f);"
)


def IdentitySettings(u: User):
    from ..routes import reset_avatar, save_profile

    return Card(
        H3('Profile'),
        Div(
            Div(
                Avatar(u, id='avatar-preview', cls='h-28 w-28 rounded-full object-cover'),
                Button('Remove avatar', cls=(ButtonT.destructive, 'whitespace-nowrap'), hx_delete=reset_avatar,
                       hx_confirm='Remove your avatar?', hx_target='#identity-settings', hx_swap='outerHTML'),
                cls='w-48 shrink-0 flex flex-col items-center gap-3'),
            Form(
                LabelInput('Nickname', name='name', value=u.name, required=True),
                Div(
                    FormLabel('Avatar', cls='block'),
                    Div(
                        Div(fh.Input(type='file', name='file', accept='image/*', id='avatar-file',
                                     onchange=AVATAR_PICKED_JS),
                            Button('Choose image', cls=(ButtonT.default, 'w-full justify-start'),
                                   submit=False, tabindex='-1'),
                            cls='w-full js-upload min-w-0 sm:max-w-xs', uk_form_custom=True),
                        Span('No file chosen', id='avatar-file-name', cls=(TextT.muted, 'min-w-0 truncate')),
                        cls='flex flex-col sm:flex-row sm:items-center gap-3'),
                    cls='space-y-2'),
                id='profile-form', hx_post=save_profile, hx_encoding='multipart/form-data',
                hx_target='#identity-settings', hx_swap='outerHTML',
                cls='min-w-0 flex-1 space-y-5'),
            cls='flex flex-col sm:flex-row gap-6 items-start'),
        id='identity-settings', cls='mg-settings-section', data_ui='identity-settings')


def CustomCssSettings():
    return Card(
        H3('Custom CSS'),
        P('Stored only in this browser and applied everywhere, including this page. '
          'Untick "Enable custom CSS" and save to go back to the default look.',
          cls=TextT.muted),
        Div(
            Div(
                FormLabel('Template', fr='custom-css-template', cls='block'),
                fh.Select(
                    fh.Option('Choose a template…', value='', selected=True),
                    fh.Option('Autumn Grove', value='/static/styles/themes/autumn-grove.css'),
                    fh.Option('Cyberpunk 2077', value='/static/styles/themes/cyberpunk-2077.css'),
                    fh.Option('Deep Sea', value='/static/styles/themes/deep-sea.css'),
                    fh.Option('Sakura', value='/static/styles/themes/sakura.css'),
                    id='custom-css-template', cls='uk-select w-full sm:max-w-sm',
                    onchange="if (this.value) { loadCustomCssTemplate(this.value, this.options[this.selectedIndex].text); this.value = ''; }"),
                P('Loading a template only places its contents in the editor. Edit it freely, then press Save changes.',
                  cls=TextT.muted),
                cls='space-y-2'),
            Div(
                CheckboxX(id='custom-css-enabled', cls='shrink-0'),
                FormLabel('Enable custom CSS', fr='custom-css-enabled', cls='m-0 cursor-pointer'),
                cls='flex items-center gap-2'),
            TextArea(id='custom-css-editor', rows=20, spellcheck='false',
                     placeholder='html:not(.dark) {\n  /* light theme */\n}\n\nhtml.dark {\n  /* dark theme */\n}',
                     cls='w-full resize-y font-mono whitespace-pre'),
            P(id='custom-css-error', cls='text-destructive', role='alert'),
            P(id='custom-css-status', cls=TextT.muted, role='status'),
            Button('Clear CSS', type='button', onclick='clearCustomCss()'),
            cls='space-y-4'),
        cls='mg-settings-section', data_ui='custom-css-settings')


def SettingsSaveBar():
    return Div(
        Button('Save changes', cls=(ButtonT.primary, 'whitespace-nowrap'), type='submit', form='profile-form',
               onclick='if (!saveCustomCss()) event.preventDefault()',
               _="""on htmx:afterRequest from body
                    if event.detail.successful put 'Saved.' into #settings-status
                    else put 'Could not save. Try again.' into #settings-status"""),
        P(id='settings-status', cls=TextT.muted, role='status'),
        cls='mg-settings-save flex items-center gap-3', data_ui='settings-save')

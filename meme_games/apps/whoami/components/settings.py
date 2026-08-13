from ...shared import *
from ...shared.settings import Setting
from ..domain import *
from meme_games.domain import Lobby, LobbyMember, User, is_host


def PrivateNotesSetting(lobby: Lobby):
    from ..routes import toggle_private_notes
    private = lobby.state.config.private_notes
    args = ('eye-off', 'Notes: private') if private else ('eye', 'Notes: shared')
    return Setting(*args, hx_post=toggle_private_notes)(hx_swap_oob='outerHTML', id='private-notes-setting')


def GameControl(lobby: Lobby, **kwargs):
    from ..routes import restart_game, start_game
    state = lobby.state
    button = (Button('Start game', hx_post=start_game, hx_swap='none', cls=(ButtonT.primary, 'w-full'))
              if state.phase == WhoAmIPhase.WAITING else
              Button('New game', hx_post=restart_game, hx_swap='none',
                     hx_confirm='Start a new game and clear cards and notes?',
                     cls=(ButtonT.destructive, 'w-full')))
    return Div(button, id='whoami-game-control', **kwargs)


def WhoAmISettings(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    if not is_host(reciever): return None
    from ..routes import update_topic
    state = lobby.state
    return Div(
        TextArea(state.config.topic, name='topic', maxlength=TOPIC_MAX, rows=2,
                 placeholder='Everything', cls='uk-textarea w-full resize-y',
                 hx_post=update_topic, hx_trigger='input changed delay:300ms', hx_swap='none'),
        P('Topic', cls=TextT.muted),
        PrivateNotesSetting(lobby),
        GameControl(lobby),
        id='whoami-settings', cls='space-y-3', **kwargs)

from meme_games.core import *
from meme_games.domain import *
from meme_games.apps.user import MemberName, UserName
from .actions import ActionRejected, ActionResult
from .utils import register_route, lobby_state

__all__ = ['ChatPanel', 'ChatLine', 'say', 'say_as']

rt = APIRouter('/chat')
register_route(rt)


def ChatLine(reciever, message: ChatMessage, **kwargs):
    own = getattr(reciever, 'uid', None) == message.uid
    return Div(
        # server-local time to start with; localTimes() restates it in the reader's own
        # zone, which is not the server's once the lobby link travels
        Time(message.at.strftime('%H:%M'), datetime=message.at.isoformat(),
             cls='mg-chat-time', title=message.at.strftime('%Y-%m-%d %H:%M')),
        Span(message.name, cls='mg-chat-author'),
        Span(message.text, cls='mg-chat-text'),
        cls=f"mg-chat-line{' mg-chat-own' if own else ''}", data_ui='chat-line', **kwargs)


def ChatPanel(reciever: LobbyMember | User, lobby: Lobby, cls='', **kwargs):
    '''Lobby-wide talk. It belongs to the lobby, not the game, so it survives a switch.'''
    return Card(
        DivLAligned(UkIcon('message-square', width=18, height=18, cls='shrink-0'),
                    H5('Chat', cls='m-0'), cls='gap-2'),
        Div(*[ChatLine(reciever, message) for message in lobby.chat],
            id='chat-messages', cls='mg-chat-messages', data_ui='chat-messages'),
        Form(Input(name='text', placeholder='Say something', maxlength=CHAT_MAX,
                   autocomplete='off', cls='uk-input min-w-0 flex-1'),
             Button('Send', cls=(ButtonT.primary, 'shrink-0 px-3')),
             hx_post=say, hx_swap='none',
             _='on htmx:afterRequest call me.reset()',
             cls='flex gap-2') if isinstance(reciever, LobbyMember) else None,
        body_cls='space-y-3 p-4',
        id='chat-panel', cls=f'mg-chat w-full min-w-0 {cls}', data_ui='chat', **kwargs)


@rt
async def say(req: Request, text: str):
    lobby, _, member = lobby_state(req)
    if not member or not lobby.say(member, text): return
    await lobby_events.publish(lobby, 'chat')


async def say_as(lobby: Lobby, member: LobbyMember, text: str) -> ActionResult:
    '''The same channel for an agent, so a table of humans and agents talks in one place.'''
    if not lobby.say(member, text):
        raise ActionRejected(f'A message must be between 1 and {CHAT_MAX} characters')
    event = await lobby_events.publish(lobby, 'chat')
    return ActionResult(True, 'Message sent', event.revision)


async def _render_chat(event: LobbyChanged, lobby: Lobby):
    if 'chat' not in event.topics or not lobby.chat: return
    message = lobby.chat[-1]
    def append(reciever, *_):
        # htmx treats an OOB element as a template for `beforeend` and inserts only its
        # children, so the line has to travel inside a carrier or it arrives unwrapped
        return Div(ChatLine(reciever, message,
                            _="init set my parentElement's scrollTop to my parentElement's scrollHeight"),
                   hx_swap_oob='beforeend:#chat-messages')
    await notify_all(lobby, append)


lobby_events.subscribe(_render_chat)

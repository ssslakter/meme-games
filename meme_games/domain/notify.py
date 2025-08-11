import asyncio
import logging
from typing import Callable, Any

from .user import User
from .lobby import Lobby, LobbyMember

logger = logging.getLogger(__name__)


async def send(u: LobbyMember, fn, *args, json=False, **kwargs):
    """Sends a message to a lobby member's websocket."""
    sock = u.ws.send_json if json else u.send
    try: await sock(fn(u, *args, **kwargs))
    except Exception as e:
        logger.error(e,exc_info=True)
        u.disconnect()


async def notify(u: User | LobbyMember,
                 fn: Callable[[LobbyMember, tuple[Any, ...]], Any], *args, json=False):
    """Sends a notification to a specific user or lobby member."""
    await send(u, fn, *args, json=json)


async def notify_all(lobby: Lobby, fn: Callable[[LobbyMember, Lobby, tuple[Any, ...]], Any], *args,
                     but: list[LobbyMember] | LobbyMember = None, filter_fn=None, json=False, **kwargs):
    '''Sends results of `fn(member:LobbyMember, lobby, *args)` for all connected members of `lobby`'''
    but = but or []
    if not isinstance(but, list): but = [but]
    tasks = [send(u, fn, lobby, *args, json=json, **kwargs) for u in lobby.sorted_members()
             if u.is_connected and (filter_fn is None or filter_fn(u)) and u not in but]
    await asyncio.gather(*tasks)

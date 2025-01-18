import asyncio
import logging
from typing import Callable, Any

from .user import User
from .lobby import Lobby, LobbyMember

logger = logging.getLogger(__name__)


async def send(u: LobbyMember, fn, *args, json=False):
    sock = u.ws.send_json if json else u.send
    try: await sock(fn(u, *args))
    except Exception as e:
        logger.error(e)
        u.disconnect()


async def notify(u: User | LobbyMember,
                 fn: Callable[[LobbyMember, tuple[Any, ...]], Any], *args, json=False):
    await send(u, fn, *args, json=json)


async def notify_all(lobby: Lobby, fn: Callable[[LobbyMember, Lobby, tuple[Any, ...]], Any], *args, filter_fn=None, json=False):
    '''Sends results of `fn(member:LobbyMember, lobby, *args)` for all connected members of `lobby`'''
    tasks = [send(u, fn, lobby, *args, json=json) for u in lobby.sorted_members()
             if u.is_connected and (filter_fn is None or filter_fn(u))]
    await asyncio.gather(*tasks)

import asyncio
from typing import Callable, Any
from .lobby import Lobby, BaseLobbyMember

async def send(u: BaseLobbyMember, fn, *args):
    try: await u.ws(fn(u, *args))
    except: u.disconnect()


async def notify_all(lobby: Lobby, fn: Callable[[BaseLobbyMember, Lobby, tuple[Any, ...]], Any], *args):
    '''Sends results of `fn(member:BaseLobbyMember, lobby, *args)` for all connected members of `lobby`'''
    tasks = [send(u, fn, lobby, *args) for u in lobby.members.values() if u.is_connected]
    await asyncio.gather(*tasks)
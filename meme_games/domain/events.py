import asyncio
import inspect
from dataclasses import dataclass
from typing import Awaitable, Callable

from .lobby import Lobby

__all__ = ['LobbyChanged', 'LobbyEventHub', 'lobby_events']


@dataclass(frozen=True)
class LobbyChanged:
    lobby_id: str
    game: str
    revision: int
    topics: frozenset[str]


Subscriber = Callable[[LobbyChanged, Lobby], Awaitable[None] | None]


class LobbyEventHub:
    """Small in-process invalidation bus; state is read from the lobby after an event."""

    def __init__(self):
        self._subscribers: set[Subscriber] = set()

    def subscribe(self, subscriber: Subscriber):
        self._subscribers.add(subscriber)
        return lambda: self._subscribers.discard(subscriber)

    async def publish(self, lobby: Lobby, *topics: str) -> LobbyChanged:
        lobby.revision += 1
        event = LobbyChanged(lobby.id, lobby.current_game, lobby.revision, frozenset(topics))
        pending = [result for subscriber in tuple(self._subscribers)
                   if inspect.isawaitable(result := subscriber(event, lobby))]
        if pending: await asyncio.gather(*pending)
        return event


lobby_events = LobbyEventHub()

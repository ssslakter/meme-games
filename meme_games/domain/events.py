import asyncio
import datetime as dt
import inspect
from dataclasses import dataclass
from typing import Awaitable, Callable

from meme_games.core import DI, DataRepository, Model
from .lobby import Lobby

__all__ = ['LobbyChanged', 'LobbyEvent', 'LobbyEventRepo', 'LobbyEventHub', 'lobby_events']


@dataclass(frozen=True)
class LobbyChanged:
    lobby_id: str
    game: str
    revision: int
    topics: frozenset[str]


@dataclass
class LobbyEvent(Model):
    """Durable, public invalidation for agents; details stay in the game state."""
    id: str
    lobby_id: str
    revision: int
    game: str
    created_at: dt.datetime

    def __post_init__(self):
        if isinstance(self.created_at, str): self.created_at = dt.datetime.fromisoformat(self.created_at)


class LobbyEventRepo(DataRepository[LobbyEvent]):
    def _set_tables(self):
        return self.db.t.lobby_events.create(**LobbyEvent.columns(), pk='id', transform=True, if_not_exists=True)

    def record(self, event: LobbyChanged):
        self.insert(LobbyEvent(f'{event.lobby_id}:{event.revision}', event.lobby_id,
                               event.revision, event.game, dt.datetime.now()))

    def after(self, lobby_id: str, revision: int) -> list[LobbyEvent]:
        rows = self.db.q('SELECT * FROM lobby_events WHERE lobby_id = ? AND revision > ? ORDER BY revision',
                         [lobby_id, revision])
        return [LobbyEvent.from_dict(row) for row in rows]


Subscriber = Callable[[LobbyChanged, Lobby], Awaitable[None] | None]


class LobbyEventHub:
    """Small in-process invalidation bus; state is read from the lobby after an event."""

    def __init__(self, repo: LobbyEventRepo):
        self._subscribers: set[Subscriber] = set()
        self.repo = repo

    def subscribe(self, subscriber: Subscriber):
        self._subscribers.add(subscriber)
        return lambda: self._subscribers.discard(subscriber)

    async def publish(self, lobby: Lobby, *topics: str) -> LobbyChanged:
        lobby.revision += 1
        event = LobbyChanged(lobby.id, lobby.current_game, lobby.revision, frozenset(topics))
        self.repo.record(event)
        if lobby.persistent:
            self.repo.db.q('UPDATE lobbies SET revision = ? WHERE id = ?', [lobby.revision, lobby.id])
        pending = [result for subscriber in tuple(self._subscribers)
                   if inspect.isawaitable(result := subscriber(event, lobby))]
        if pending: await asyncio.gather(*pending)
        return event


DI.register_service(LobbyEventRepo)
lobby_events = LobbyEventHub(DI.get(LobbyEventRepo))

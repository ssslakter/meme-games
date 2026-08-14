import asyncio
import datetime as dt
import inspect
import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from meme_games.core import DI, DataRepository, Model
from .lobby import Lobby

__all__ = ['LobbyChanged', 'LobbyEvent', 'LobbyEventRepo', 'LobbyEventHub', 'lobby_events']

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LobbyChanged:
    lobby_id: str
    game: str
    revision: int
    topics: frozenset[str]


@dataclass
class LobbyEvent(Model):
    """Durable, public record of what moved; the details stay in the game state."""
    id: str
    lobby_id: str
    revision: int
    game: str
    created_at: dt.datetime
    topics: str = ''  # space separated, so rows written before this field read as none
    data: str = ''    # JSON facts as they were when this happened

    def __post_init__(self):
        if isinstance(self.created_at, str): self.created_at = dt.datetime.fromisoformat(self.created_at)
        self.topics, self.data = self.topics or '', self.data or ''

    def topic_list(self) -> list[str]: return self.topics.split()

    def facts(self) -> dict:
        try: return json.loads(self.data) if self.data else {}
        except ValueError: return {}


class LobbyEventRepo(DataRepository[LobbyEvent]):
    def _set_tables(self):
        return self.db.t.lobby_events.create(**LobbyEvent.columns(), pk='id', transform=True, if_not_exists=True)

    def record(self, event: LobbyChanged, facts: dict = None):
        self.insert(LobbyEvent(f'{event.lobby_id}:{event.revision}', event.lobby_id,
                               event.revision, event.game, dt.datetime.now(),
                               ' '.join(sorted(event.topics)),
                               json.dumps(facts) if facts else ''))

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
        # Replaced by the app layer. An event is read long after it happened, so what
        # happened has to be written down now - it cannot be looked up later.
        self.capture: Callable[[Lobby, frozenset[str]], dict[str, Any]] = lambda lobby, topics: {}

    def _facts(self, lobby: Lobby, topics: frozenset[str]) -> dict:
        try: return self.capture(lobby, topics)
        except Exception:
            logger.exception('Capturing event facts failed')
            return {}

    def subscribe(self, subscriber: Subscriber):
        self._subscribers.add(subscriber)
        return lambda: self._subscribers.discard(subscriber)

    async def publish(self, lobby: Lobby, *topics: str) -> LobbyChanged:
        lobby.revision += 1
        event = LobbyChanged(lobby.id, lobby.current_game, lobby.revision, frozenset(topics))
        self.repo.record(event, self._facts(lobby, event.topics))
        if lobby.persistent:
            self.repo.db.q('UPDATE lobbies SET revision = ? WHERE id = ?', [lobby.revision, lobby.id])
        pending = [result for subscriber in tuple(self._subscribers)
                   if inspect.isawaitable(result := subscriber(event, lobby))]
        if pending: await asyncio.gather(*pending)
        return event


DI.register_service(LobbyEventRepo)
lobby_events = LobbyEventHub(DI.get(LobbyEventRepo))

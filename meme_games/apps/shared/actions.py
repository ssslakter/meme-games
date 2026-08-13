import asyncio
from collections import defaultdict
from dataclasses import dataclass

from meme_games.domain import Lobby, LobbyService, lobby_events

__all__ = ['ActionRejected', 'ActionResult', 'GameActions']


class ActionRejected(ValueError): pass


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    message: str
    revision: int


# TODO: Route Alias mutations through this boundary before adding agent support.
# TODO: Do the same for Video if it gains server-side gameplay mutations.
class GameActions:
    """Serialize, persist, and publish game mutations."""

    def __init__(self, lobbies: LobbyService):
        self.lobbies = lobbies
        self._locks = defaultdict(asyncio.Lock)

    async def _change(
        self, lobby: Lobby, mutate, message: str, topic='game',
        rejected='Action is not legal now',
    ) -> ActionResult:
        async with self._locks[lobby.id]:
            if not mutate(): raise ActionRejected(rejected)
            self.lobbies.update(lobby)
            event = await lobby_events.publish(lobby, topic)
            return ActionResult(True, message, event.revision)

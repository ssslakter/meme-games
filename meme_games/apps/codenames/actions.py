import asyncio
from collections import defaultdict
from dataclasses import dataclass

from meme_games.core import DI
from meme_games.domain import Lobby, LobbyMember, LobbyService, is_host, lobby_events
from meme_games.apps.word_packs.domain import WordPackRepo

from .domain import CodenamesState, GamePhase, TeamColor

__all__ = ['ActionRejected', 'ActionResult', 'CodenamesActions', 'codenames_actions']


class ActionRejected(ValueError): pass


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    message: str
    revision: int


class CodenamesActions:
    """The shared application boundary used by browser routes and agent calls."""

    def __init__(self, lobbies: LobbyService, wordpacks: WordPackRepo):
        self.lobbies, self.wordpacks = lobbies, wordpacks
        self._locks = defaultdict(asyncio.Lock)

    async def _change(self, lobby: Lobby, mutate, message: str, topic='game', rejected='Action is not legal now') -> ActionResult:
        async with self._locks[lobby.id]:
            if not mutate(): raise ActionRejected(rejected)
            self.lobbies.update(lobby)
            event = await lobby_events.publish(lobby, topic)
            return ActionResult(True, message, event.revision)

    async def join_team(self, lobby: Lobby, member: LobbyMember, team: str):
        try: team = TeamColor(team)
        except ValueError: raise ActionRejected('Unknown team')
        def mutate():
            if lobby.locked or not lobby.state.join(member, team): return False
            member.play()
            return True
        return await self._change(lobby, mutate, f'Joined the {team.value} team', 'roster', 'Teams are locked')

    async def set_role(self, lobby: Lobby, member: LobbyMember, role: str):
        if role not in ('operative', 'spymaster'): raise ActionRejected('Unknown role')
        return await self._change(
            lobby, lambda: lobby.state.set_spymaster(member, role == 'spymaster'),
            f'Role set to {role}', rejected='Choose a team first, or use its available spymaster seat')

    async def select_pack(self, lobby: Lobby, member: LobbyMember, pack_id: str):
        pack = self.wordpacks.get_by_id(pack_id)
        def mutate():
            if not is_host(member) or lobby.state.phase != GamePhase.WAITING or not pack: return False
            lobby.state.wordpack = pack
            return True
        return await self._change(lobby, mutate, 'Wordpack selected', 'settings', 'Cannot select that wordpack')

    async def start(self, lobby: Lobby, member: LobbyMember):
        def mutate():
            if not is_host(member) or not lobby.state.start(): return False
            lobby.lock()
            return True
        return await self._change(lobby, mutate, 'Game started', rejected='Game is not ready to start')

    async def give_clue(self, lobby: Lobby, member: LobbyMember, clue: str, number: int):
        return await self._change(
            lobby, lambda: lobby.state.give_clue(member, clue, number), 'Clue submitted', rejected='Invalid clue')

    async def reveal_card(self, lobby: Lobby, member: LobbyMember, card_id: str):
        return await self._change(
            lobby, lambda: lobby.state.reveal(member, card_id), 'Card revealed', rejected='You cannot reveal that card')

    async def end_turn(self, lobby: Lobby, member: LobbyMember):
        state: CodenamesState = lobby.state
        def mutate():
            return (state.phase == GamePhase.GUESSING and state.team_of(member) == state.turn
                    and member.uid not in state.spymasters and state.end_turn())
        return await self._change(lobby, mutate, 'Turn ended', rejected='You cannot end this turn')

    async def spectate(self, lobby: Lobby, member: LobbyMember):
        def mutate():
            if lobby.locked or not member.is_player: return False
            self.lobbies.spectate(member, lobby)
            return True
        return await self._change(lobby, mutate, 'Now spectating', 'roster', 'Cannot spectate while the game is locked')

    async def restart(self, lobby: Lobby, member: LobbyMember):
        def mutate():
            if not is_host(member): return False
            lobby.state.restart()
            lobby.unlock()
            return True
        return await self._change(lobby, mutate, 'Game restarted', rejected='Only the host can restart')


codenames_actions = CodenamesActions(DI.get(LobbyService), DI.get(WordPackRepo))

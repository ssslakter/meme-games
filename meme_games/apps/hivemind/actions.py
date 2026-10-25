__all__ = ['ActionRejected', 'ActionResult', 'HiveMindActions', 'hivemind_actions']

from meme_games.core import DI
from meme_games.domain import Lobby as _Lobby, LobbyMember, LobbyService, is_host
from meme_games.apps.shared.actions import ActionRejected, ActionResult, GameActions
from meme_games.apps.word_packs.domain import WordPackRepo

from .domain import HiveMindState, HivePhase

Lobby = _Lobby[HiveMindState]


class HiveMindActions(GameActions):
    """The application boundary every browser route goes through."""

    def __init__(self, lobbies: LobbyService, wordpacks: WordPackRepo):
        super().__init__(lobbies)
        self.wordpacks = wordpacks

    @staticmethod
    def uids(lobby: Lobby) -> list[str]:
        return [member.uid for member in lobby.sorted_members() if member.is_player]

    async def join(self, lobby: Lobby, member: LobbyMember):
        def mutate():
            if member is None or lobby.locked or member.is_player: return False
            member.play()
            return True
        return await self._change(lobby, mutate, 'Joined the game', 'roster', 'The game is locked')

    async def submit(self, lobby: Lobby, member: LobbyMember, text: str):
        state: HiveMindState = lobby.state
        def mutate():
            return member is not None and member.is_player and state.submit(member.uid, text)
        return await self._change(lobby, mutate, 'Answer saved', 'progress',
                                  'An answer must be 1 to 60 characters')

    async def advance(self, lobby: Lobby, member: LobbyMember):
        """Host-only, and the only way a round moves: open answers get revealed, a
        revealed round gets the next question."""
        state: HiveMindState = lobby.state
        def mutate():
            if not is_host(member): return False
            return state.reveal() if state.phase == HivePhase.WRITING else state.next_round()
        return await self._change(lobby, mutate, 'Round moved on', 'game',
                                  'Only the host can move the round on')

    async def start(self, lobby: Lobby, member: LobbyMember):
        def mutate():
            if not is_host(member) or not lobby.state.start(self.uids(lobby)): return False
            lobby.lock()
            return True
        return await self._change(lobby, mutate, 'Game started', 'game',
                                  'Need at least two players')

    async def restart(self, lobby: Lobby, member: LobbyMember):
        def mutate():
            if not is_host(member): return False
            lobby.state.restart()
            lobby.unlock()
            return True
        return await self._change(lobby, mutate, 'Game restarted', 'game',
                                  'Only the host can restart')

    async def select_pack(self, lobby: Lobby, member: LobbyMember, pack_id: str):
        """Host-only, between matches: the deck a lobby plays its questions from."""
        pack = self.wordpacks.get_by_id(pack_id)
        def mutate():
            if not is_host(member) or lobby.state.phase != HivePhase.WAITING or not pack: return False
            lobby.state.wordpack = pack
            return True
        return await self._change(lobby, mutate, 'Deck selected', 'game',
                                  'Cannot select that wordpack')

    async def update_settings(self, lobby: Lobby, member: LobbyMember, total_rounds: int):
        """Between matches only, so a round count cannot change under a match in play."""
        state: HiveMindState = lobby.state
        def mutate():
            if not is_host(member) or state.phase != HivePhase.WAITING: return False
            return state.set_total_rounds(total_rounds)
        return await self._change(lobby, mutate, 'Settings updated', 'game',
                                  'Rounds must be 1 to 20, and only between games')


hivemind_actions = HiveMindActions(DI.get(LobbyService), DI.get(WordPackRepo))

__all__ = ['ActionRejected', 'ActionResult', 'HiveMindActions', 'hivemind_actions']

import asyncio

from meme_games.core import DI
from meme_games.domain import Lobby as _Lobby, LobbyMember, LobbyService, is_host
from meme_games.apps.shared.actions import ActionRejected, ActionResult, GameActions
from meme_games.apps.word_packs.domain import WordPackRepo

from .domain import ANSWER_MAX, ANSWERS_PER_ROUND, HIVEMIND, HiveMindState, HivePhase

Lobby = _Lobby[HiveMindState]


class HiveMindActions(GameActions):
    """The application boundary every browser route goes through."""

    def __init__(self, lobbies: LobbyService, wordpacks: WordPackRepo):
        super().__init__(lobbies)
        self.wordpacks = wordpacks
        self._watched: dict[str, int] = {}

    @staticmethod
    def uids(lobby: Lobby) -> list[str]:
        return [member.uid for member in lobby.sorted_members() if member.is_player]

    def _watch_round(self, lobby: Lobby):
        """One watcher per armed round clock; the token keeps stale ones from firing."""
        state: HiveMindState = lobby.state
        if not state.seconds or state.phase != HivePhase.WRITING: return
        if self._watched.get(lobby.id) == state.timer_token: return
        self._watched[lobby.id] = state.timer_token
        asyncio.create_task(self._round_timeout(lobby, state, state.timer_token))

    async def _round_timeout(self, lobby: Lobby, state: HiveMindState, token: int):
        await state.timer.sleep()
        if (lobby.current_game != HIVEMIND or lobby.state is not state
                or state.timer_token != token or not state.timer.finished): return
        try: await self._change(lobby, state.timeout, 'Time is up', 'game')
        except ActionRejected: pass

    async def join(self, lobby: Lobby, member: LobbyMember):
        def mutate():
            if member is None or lobby.locked or member.is_player: return False
            member.play()
            return True
        return await self._change(lobby, mutate, 'Joined the game', 'roster', 'The game is locked')

    async def set_word(self, lobby: Lobby, member: LobbyMember, index: int, text: str):
        """A private autosave: nobody else's view changes until the round closes."""
        state: HiveMindState = lobby.state
        def mutate():
            return member is not None and member.is_player and state.set_word(member.uid, index, text)
        return await self._change(lobby, mutate, 'Word saved', (), 'Cannot save that word')

    async def set_ready(self, lobby: Lobby, member: LobbyMember, is_ready: bool = True,
                        words: list[str] | None = None):
        """Save this player's list, then mark them done. The render step decides whether
        that is a count change or the reveal: a full board swap while others are still
        typing would wipe whatever they have not saved yet."""
        state: HiveMindState = lobby.state
        def mutate():
            if member is None or not member.is_player: return False
            if is_ready and words is not None:
                cleaned = [' '.join(str(word or '').split()) for word in words[:ANSWERS_PER_ROUND]]
                if any(len(word) > ANSWER_MAX for word in cleaned): return False
                for index, word in enumerate(cleaned):
                    if not state.set_word(member.uid, index, word): return False
            return state.set_ready(member.uid, is_ready)
        # 'status' while the round stays open, so the page only refreshes the count.
        # The subscriber sends the whole board once the phase has left writing.
        return await self._change(lobby, mutate, 'Ready' if is_ready else 'Not ready', 'status',
                                  'The round is already closed')

    async def edit_word(self, lobby: Lobby, member: LobbyMember, uid: str, index: int, text: str):
        """One cell. Published on its own so the other cells stay as the reader left them."""
        state: HiveMindState = lobby.state
        def mutate():
            if member is None or (member.uid != uid and not is_host(member)): return False
            return state.edit_word(uid, index, text)
        return await self._change(lobby, mutate, 'Word edited', 'edit',
                                  "Only that word's author or the host can change it")

    async def advance(self, lobby: Lobby, member: LobbyMember):
        """Host-only, and the only way a round moves: an open round gets revealed, a
        revealed round gets the next question."""
        state: HiveMindState = lobby.state
        def mutate():
            if not is_host(member): return False
            return state.reveal() if state.phase == HivePhase.WRITING else state.next_round()
        result = await self._change(lobby, mutate, 'Round moved on', 'game',
                                    'Only the host can move the round on')
        self._watch_round(lobby)
        return result

    async def start(self, lobby: Lobby, member: LobbyMember):
        def mutate():
            if not is_host(member) or not lobby.state.start(self.uids(lobby)): return False
            lobby.lock()
            return True
        result = await self._change(lobby, mutate, 'Game started', 'game',
                                    'Need at least two players')
        self._watch_round(lobby)
        return result

    async def restart(self, lobby: Lobby, member: LobbyMember):
        def mutate():
            if not is_host(member): return False
            lobby.state.restart()
            lobby.unlock()
            return True
        return await self._change(lobby, mutate, 'Game restarted', 'game',
                                  'Only the host can restart')

    async def select_pack(self, lobby: Lobby, member: LobbyMember, pack_id: str,
                          slot: str = 'prompts'):
        """Host-only, before the match and between rounds. `topics` is the deck a topics round deals from."""
        pack = self.wordpacks.get_by_id(pack_id)
        def mutate():
            state: HiveMindState = lobby.state
            if not is_host(member) or state.phase == HivePhase.WRITING or not pack: return False
            if slot == 'topics':
                state.topicpack = pack
                if state.phase == HivePhase.REVEAL: state._shuffle_topics()
            else:
                state.wordpack = pack
                if state.phase == HivePhase.REVEAL: state._reshuffle()
            return True
        return await self._change(lobby, mutate, 'Deck selected', 'game',
                                  'Cannot select that wordpack')

    async def update_settings(self, lobby: Lobby, member: LobbyMember, total_rounds: int,
                              seconds: int, same: bool = False, different: bool = False,
                              topics: bool = False):
        """Before the match and between rounds. A round that is still being written keeps its clock."""
        state: HiveMindState = lobby.state
        def mutate():
            if not is_host(member) or state.phase == HivePhase.WRITING: return False
            if not state.set_total_rounds(total_rounds): return False
            if not state.set_seconds(seconds): return False
            return state.set_kinds(same, different, topics)
        return await self._change(lobby, mutate, 'Settings updated', 'game',
                                  'Turn on at least one of same, different and topics. '
                                  'Rounds must be 1 to 20, seconds 0 to 900, and only between rounds')


hivemind_actions = HiveMindActions(DI.get(LobbyService), DI.get(WordPackRepo))

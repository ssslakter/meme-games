import asyncio

from meme_games.core import DI
from meme_games.domain import Lobby, LobbyMember, LobbyService, is_host
from meme_games.apps.shared.actions import ActionRejected, ActionResult, GameActions
from meme_games.apps.word_packs.domain import WordPackRepo

from . import domain
from .domain import CODENAMES, CodenamesState, GamePhase, TeamColor

__all__ = ['ActionRejected', 'ActionResult', 'CodenamesActions', 'codenames_actions']


class CodenamesActions(GameActions):
    """The shared application boundary used by browser routes and agent calls."""

    def __init__(self, lobbies: LobbyService, wordpacks: WordPackRepo):
        super().__init__(lobbies)
        self.wordpacks = wordpacks
        self._watched: dict[str, int] = {}

    def _watch_turn(self, lobby: Lobby):
        '''One watcher per armed turn timer; the token keeps stale ones from firing.'''
        state: CodenamesState = lobby.state
        if not state.turn_seconds() or self._watched.get(lobby.id) == state.timer_token: return
        self._watched[lobby.id] = state.timer_token
        asyncio.create_task(self._turn_timeout(lobby, state, state.timer_token))

    async def _turn_timeout(self, lobby: Lobby, state: CodenamesState, token: int):
        await state.timer.sleep()
        if (lobby.current_game != CODENAMES or lobby.state is not state
                or state.timer_token != token or not state.timer.finished): return
        try: await self._change(lobby, state.timeout, 'Time is up', ('game', 'turn'))
        except ActionRejected: pass
        self._watch_turn(lobby)

    async def _commit_vote(self, lobby: Lobby, state: CodenamesState, version: int, card_id: str):
        await asyncio.sleep(domain.COMMIT_SECONDS)
        if lobby.state is not state or state.votes_version != version: return
        if state.consensus() != card_id: return
        member = lobby.members.get(next(iter(state.votes), ''))
        if not member: return
        try: await self.reveal_card(lobby, member, card_id)
        except ActionRejected: pass

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
            f'Role set to {role}', ('game', 'roles'),
            rejected='Choose a team first, or use its available spymaster seat')

    async def select_pack(self, lobby: Lobby, member: LobbyMember, pack_id: str):
        pack = self.wordpacks.get_by_id(pack_id)
        def mutate():
            if not is_host(member) or lobby.state.phase != GamePhase.WAITING or not pack: return False
            lobby.state.wordpack = pack
            return True
        return await self._change(lobby, mutate, 'Wordpack selected', 'settings', 'Cannot select that wordpack')

    async def update_settings(self, lobby: Lobby, member: LobbyMember, clue_seconds: int, guess_seconds: int):
        def mutate():
            if not is_host(member): return False
            lobby.state.clue_seconds = max(0, clue_seconds)
            lobby.state.guess_seconds = max(0, guess_seconds)
            lobby.state._arm_timer()
            return True
        result = await self._change(lobby, mutate, 'Settings updated', 'settings',
                                    rejected='Only the host can change settings')
        self._watch_turn(lobby)
        return result

    async def shuffle_teams(self, lobby: Lobby, member: LobbyMember):
        return await self._change(
            lobby, lambda: is_host(member) and lobby.state.shuffle_teams(), 'Teams shuffled',
            ('game', 'roles'), rejected='Teams can only be shuffled before the game')

    async def pause(self, lobby: Lobby, member: LobbyMember):
        state: CodenamesState = lobby.state
        def mutate():
            if not is_host(member) or not state.turn_seconds(): return False
            state.timer.resume() if state.timer.paused else state.timer.pause()
            return True
        return await self._change(lobby, mutate, 'Timer toggled', 'game', rejected='Nothing to pause')

    async def start(self, lobby: Lobby, member: LobbyMember):
        def mutate():
            if not is_host(member) or not lobby.state.start(): return False
            lobby.lock()
            return True
        result = await self._change(lobby, mutate, 'Game started', ('game', 'start'),
                                    rejected='Game is not ready to start')
        self._watch_turn(lobby)
        return result

    async def give_clue(self, lobby: Lobby, member: LobbyMember, clue: str, number: int):
        result = await self._change(
            lobby, lambda: lobby.state.give_clue(member, clue, number), 'Clue submitted', ('game', 'clue'),
            rejected='Invalid clue')
        self._watch_turn(lobby)
        return result

    async def vote(self, lobby: Lobby, member: LobbyMember, card_id: str):
        state: CodenamesState = lobby.state
        result = await self._change(
            lobby, lambda: state.vote(member, card_id), 'Pick registered', ('game', 'vote'),
            rejected='You cannot pick that card')
        if state.consensus() == card_id:
            asyncio.create_task(self._commit_vote(lobby, state, state.votes_version, card_id))
        return result

    async def reveal_card(self, lobby: Lobby, member: LobbyMember, card_id: str):
        result = await self._change(
            lobby, lambda: lobby.state.reveal(member, card_id), 'Card revealed', ('game', 'reveal'),
            rejected='You cannot reveal that card')
        self._watch_turn(lobby)
        return result

    async def end_turn(self, lobby: Lobby, member: LobbyMember):
        state: CodenamesState = lobby.state
        def mutate():
            return (state.phase == GamePhase.GUESSING and state.team_of(member) == state.turn
                    and member.uid not in state.spymasters and state.end_turn())
        result = await self._change(lobby, mutate, 'Turn ended', ('game', 'turn'),
                                    rejected='You cannot end this turn')
        self._watch_turn(lobby)
        return result

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
        return await self._change(lobby, mutate, 'Game restarted', ('game', 'restart'),
                                  rejected='Only the host can restart')


codenames_actions = CodenamesActions(DI.get(LobbyService), DI.get(WordPackRepo))

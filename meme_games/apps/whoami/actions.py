from meme_games.core import DI
from meme_games.domain import Lobby, LobbyMember, LobbyService, is_host
from meme_games.apps.shared.actions import ActionRejected, ActionResult, GameActions

from .domain import CARD_MAX, NOTES_MAX, TOPIC_MAX, WhoAmIPhase, WhoAmIState

__all__ = ['ActionRejected', 'ActionResult', 'WhoAmIActions', 'whoami_actions']


class WhoAmIActions(GameActions):

    @staticmethod
    def order(lobby: Lobby) -> list[str]:
        return [member.uid for member in lobby.sorted_members() if member.is_player]

    async def set_topic(self, lobby: Lobby, member: LobbyMember, topic: str):
        def mutate():
            if not is_host(member) or len(topic) > TOPIC_MAX: return False
            lobby.state.config.topic = topic
            return True
        return await self._change(lobby, mutate, 'Topic updated', 'topic', 'Only the host can change the topic')

    async def write_card(self, lobby: Lobby, member: LobbyMember, text: str):
        state: WhoAmIState = lobby.state
        order = state.turn_order if state.phase == WhoAmIPhase.PLAYING else self.order(lobby)
        target = state.next_player(member.uid, order)
        def mutate():
            if not member.is_player or not target or len(text) > CARD_MAX: return False
            state.player(target).set_label(text)
            return True
        return await self._change(lobby, mutate, 'Card updated', f'card:{target}', 'You cannot write that card')

    async def write_note(self, lobby: Lobby, member: LobbyMember, text: str):
        def mutate():
            if not member.is_player or len(text) > NOTES_MAX: return False
            lobby.state.player(member.uid).set_notes(text)
            return True
        return await self._change(lobby, mutate, 'Notes updated', f'notes:{member.uid}', 'Only players have notes')

    async def start(self, lobby: Lobby, member: LobbyMember):
        def mutate():
            if not is_host(member) or not lobby.state.start(self.order(lobby)): return False
            lobby.lock()
            return True
        return await self._change(
            lobby, mutate, 'Game started', 'game', 'Need at least two players and a card for everyone')

    async def restart(self, lobby: Lobby, member: LobbyMember):
        def mutate():
            if not is_host(member): return False
            lobby.state.restart()
            lobby.unlock()
            return True
        return await self._change(lobby, mutate, 'Game restarted', 'game', 'Only the host can restart')

    async def ask_question(self, lobby: Lobby, member: LobbyMember, text: str):
        state: WhoAmIState = lobby.state
        return await self._change(
            lobby, lambda: state.ask(member, text), 'Question asked', 'question',
            lambda: state.ask_rejection(member, text) or 'Question is not legal now')

    async def answer_question(self, lobby: Lobby, member: LobbyMember, answer: str):
        return await self._change(
            lobby, lambda: lobby.state.answer(member, answer), 'Question answered', 'question',
            'Only the card author can answer the pending question')

    async def end_turn(self, lobby: Lobby, member: LobbyMember):
        return await self._change(
            lobby, lambda: lobby.state.end_turn(member), 'Turn ended', 'turn',
            'Only the active player can end the turn')


whoami_actions = WhoAmIActions(DI.get(LobbyService))
